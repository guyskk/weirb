from setuptools import setup, find_packages

setup(
    name='weirb',
    version='0.6.1',
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
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    python_requires='>=3.6',
    install_requires=[
        'newio>=0.6.1',
        'validr>=1.0.1',
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
    extras_require={
        'dev': [
            'invoke==1.0.0',
            'pytest==3.6.1',
            'pytest-cov==2.5.1',
            'bumpversion==0.5.3',
            'coloredlogs==10.0',
            'twine==1.11.0',
            'pre-commit==1.10.2',
            'codecov==2.0.15',
        ],
    },
    entry_points={
        'console_scripts': [
            'weirb=weirb.cli:cli',
        ],
    },
)
