"""
Main entry point for Clarity extensions in the SNP&SEQ installation
"""
from setuptools import find_packages, setup
from clarity_ext import VERSION

dependencies = ['click', 'genologics', 'requests-cache', 'pyyaml', 'nose', 'PyPDF2',
                'lxml', 'coverage', 'pep8radius', 'mock', 'jinja2', 'python-levenshtein',
                'fuzzywuzzy', 'pandas', 'xlrd']

setup(
    name='clarity-ext',
    version=VERSION,
    url='https://github.com/withrocks/clarity-ext',
    author='withrocks',
    author_email='withrocks',
    description='Main entry point for Clarity extensions in the SNP&SEQ installation',
    long_description=__doc__,
    packages=find_packages(exclude=['tests']),
    package_data={'': ['*.j2', '*.txt', 'README']},
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=dependencies,
    entry_points={
        'console_scripts': [
            'clarity-ext = clarity_ext.cli:main',
            'clarity-data = clarity_ext.data_cli:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Operating System :: MacOS',
        'Operating System :: Unix',
        'Operating System :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
