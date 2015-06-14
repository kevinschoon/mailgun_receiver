__author__ = 'kevinschoon@gmail.com'

from setuptools import setup, find_packages

setup(
    name='mailgun_receiver',
    version='0.0.1',
    packages=find_packages(),
    package_dir={'mg_receiver': 'mg_receiver'},
    entry_points={'console_scripts': ['mg_receiver = mg_receiver.server:main']},
    install_requires=['aiohttp', 'pyyaml'],
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.4'
    ]
)
