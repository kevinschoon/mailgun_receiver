__author__ = 'kevinschoon@gmail.com'

import os
import argparse
import asyncio
import hashlib
import hmac
import json
import logging
import dbm

from yaml import load
from aiohttp import web, request, BasicAuth

logger = logging.getLogger(__name__)


class MgSubscriber:
    """
    Add users defined in the "subscriptions" section for mg.yml to the specified mailing list.
    """

    mg_api_endpoint = 'https://api.mailgun.net/v3/lists/{}/members'

    def __init__(self, api_key, queue, config):
        self.api_key = api_key
        self.queue = queue
        self.config = config

    def _add_user_to_mailing_list(self, to, rpl):
        config = self.config[to]
        logging.info('Subscribing user {} to mailing list: {}'.format(rpl, config['alias']))
        resp = yield from request(
            method='POST',
            url=self.mg_api_endpoint.format(config['alias']),
            data={'address': rpl, 'subscribed': 'yes'}
        )
        response = yield from resp.read()
        if resp.status == 200:
            logging.info('Processed request: {}'.format(response))
        else:
            logging.warning('Error processing mailing list update request: {}'.format(response))

    @asyncio.coroutine
    def _run(self):
        while True:
            headers = yield from self.queue.get()
            frm, to, rpl = MgReceiver.process_headers(headers)
            if to in self.config:
                yield from self._add_user_to_mailing_list(to, rpl)
            else:
                logging.warning('Unknown sender address {}'.format(to))

    def start(self):
        return self._run()


class MgSender:
    """
    Reach out to the user who signed up with a specified message template.
    """

    mg_api_endpoint = 'https://api.mailgun.net/v3/{}/messages'

    def __init__(self, api_key, queue, config):
        self.api_key = api_key
        self.queue = queue
        self.config = config
        self.auth = BasicAuth(login='api', password=self.api_key)

    @asyncio.coroutine
    def _send_acknowledgement(self, to, rpl):
        config = self.config[to]
        logging.info('Sending acknowledgement: {} {}'.format(to, rpl))
        resp = yield from request(
            method='POST',
            url=self.mg_api_endpoint.format(config['domain']),
            auth=self.auth,
            data={"to": [rpl], "from": config['from'], "subject": config['subject'], "text": config['text']}
        )
        response = yield from resp.read()
        if resp.status == 200:
            logging.info('Processed request: {}'.format(response))
        else:
            logging.warning('Error sending user acknowledgement: {}'.format(response))

    @asyncio.coroutine
    def _run(self):
        while True:
            headers = yield from self.queue.get()
            frm, to, rpl = MgReceiver.process_headers(headers)
            if to in self.config:
                yield from self._send_acknowledgement(to, rpl)
            else:
                logging.warning('Unknown sender address: {}'.format(to))

    def start(self):
        return self._run()


class MgReceiver:
    """
    Setup a server and process messages send by Mailgun's webhooks.
    """
    def __init__(self, api_key, config, port=9898, db_path='mg.db'):
        self.key = api_key
        self.port = port
        self.db_path = db_path
        self.config = config
        self.loop = asyncio.get_event_loop()
        self.sender_q = asyncio.Queue()
        self.subscriber_q = asyncio.Queue()
        self.sender = MgSender(api_key=self.key, queue=self.sender_q, config=config['senders'])
        self.subscriber = MgSubscriber(api_key=self.key, queue=self.subscriber_q, config=['subscribers'])
        self.app = web.Application(loop=self.loop)

    def _verify(self, token, timestamp, signature):
        token = bytes(token, 'utf-8')
        timestamp = bytes(timestamp, 'utf-8')
        api_key = bytes(self.key, 'utf-8')
        match = hmac.new(key=api_key, msg=timestamp + token, digestmod=hashlib.sha256).hexdigest()
        return str(match) == signature

    @staticmethod
    def process_headers(headers):
        msg_from = [x for x in headers if 'From' in x][0][1]
        msg_to = [x for x in headers if 'To' in x][0][1]
        reply_to = [x for x in headers if 'Reply-To' in x][0][1]
        return msg_from, msg_to, reply_to

    @asyncio.coroutine
    def _handle(self, request: web.Request):
        logging.info('Processing request: {} {}'.format(request.host, request.headers))
        post = yield from request.post()
        token, timestamp, signature = post['token'], post['timestamp'], post['signature']
        headers = post['message-headers']
        if self._verify(token=token, timestamp=timestamp, signature=signature):
            response = yield from self._process(json.loads(headers))
            return response
        return web.Response(status=401, reason='Unauthorized')

    @asyncio.coroutine
    def _process(self, headers):
        try:
            to, frm, reply = self.process_headers(headers)
        except IndexError:
            return web.Response(status=200)
        with dbm.open(self.db_path, 'c') as db:
            if reply not in db:
                db[reply] = json.dumps({'to': to, 'from': frm, 'headers': headers})
                yield from self.sender_q.put(headers)
                yield from self.subscriber_q.put(headers)
                return web.Response(status=200, body='Thank you'.encode('utf-8'))
            else:
                logging.warning('User {} already subscribed, not doin nothin\''.format(reply))
                return web.Response(status=406, body='User already processed'.encode('utf-8'))

    @asyncio.coroutine
    def _run(self):
        self.app.router.add_route('POST', '/mg/hook', self._handle)
        yield from self.loop.create_server(self.app.make_handler(), '0.0.0.0', self.port)
        logging.info("Server running @ http://0.0.0.0:9898")

    def start(self):

        tasks = [
            asyncio.async(self._run()),
            asyncio.async(self.sender.start()),
            asyncio.async(self.subscriber.start())
        ]

        try:
            self.loop.run_until_complete(asyncio.wait(tasks))
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(prog='Mailgun Receiver', description='Listen to Mailgun events and do stuff')
    parser.add_argument('-a', '--api_key', default=os.getenv('MAILGUN_API_KEY'))
    parser.add_argument('-d', '--db_path', default='mg.db')
    parser.add_argument('-c', '--cfg', default='mg.yml')
    parser.add_argument('-l', '--level', default='INFO')
    args = parser.parse_args()

    logging.basicConfig(level=args.level, format='%(asctime)s - %(levelname)s - %(name)s.%(module)s - %(message)s')

    with open(args.cfg) as fp:
        config = load(fp.read())
        mg = MgReceiver(api_key=args.api_key, config=config, db_path=args.db_path)
        mg.start()

if __name__ == '__main__':
    main()
