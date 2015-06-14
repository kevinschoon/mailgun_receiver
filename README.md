## Mailgun Receiver

Mailgun Receiver is an asynchronous HTTP callback server for [Mailgun](https://mailgun.com).
It requires Python 3.4 and is built using the [aiohttp](http://aiohttp.readthedocs.org/) library.

Install
-------

```bash
git clone git@github.com:kevinschoon/mailgun_receiver.git
cd mailgun_receiver
pip install .
```

Docker
------
You can build a Docker container from the root of the repository:

```bash
docker build -t mailgun_receiver .
```

Configuration
-------------

We use the YAML format to configure rules to do one of two things currently:  
* Notify a user who has sent an e-mail to Mailgun with the `Reply-To` header specified in mail headers.
* Subscribe the user to a Mailgun mailing list.

You'll need to configure mailgun with the mailing list : `inquiry@yourdomain.com` and then setup a `Delivered messages` [webhook](https://documentation.mailgun.com/user_manual.html#webhooks) to subscribe to your server's callback address.

```yaml
senders:
  inquiry@yourdomain.com: # Catch any e-mail send to "inquiry@yourdomain.com"
    domain: yourdomain.com
    from: no-reply@yourdomain.com
    subject: Thanks for reaching out!
    html: |
        <h3> Thanks for reaching out! </h3>
        <p> Someone will contact you shortly about your inquiry.</p>
        - The YourCompany Team
subscribers:  # New users are added to the inquiry@somedomain.com mailing list.
  inquiry@yourdomain.com:
    alias: news@yourdomain.com
```

Running
-------
Once you have your configuration file setup you can run the server from your command line:

```bash
MAILGUN_API_KEY=key_12345 mg_reciever -d mg.db -c mg.yml
>>> INFO:root:Server running @ http://0.0.0.0:9898
```

TODO
----

* Tests
* Better configuration system
* Full callback support for Mailgun
* Complete documentation
