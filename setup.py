from setuptools import setup

setup(
    name='weirb',
    version='0.2',
    description='Weird Web Framework',
    url='https://github.com/guyskk/weirb',
    author='guyskk',
    author_email='guyskk@qq.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
    ],
    packages=['weirb'],
    python_requires='>=3.6',
    install_requires=[
        'newio>=0.4',
        'newio-kernel>=0.4',
        'toml>=0.9.4',
        'click>=6.7',
        'gunicorn>=19.8',
        'httptools>=0.0.11',
        'coloredlogs>=10.0',
        'zope.interface>=4.5',
        'werkzeug>=0.14.1',
        'simiki>=1.6',
        'mako>=1.0',
    ],
    entry_points={
        'console_scripts': [
            'weirb=weirb.cli:cli',
        ],
    },
)
