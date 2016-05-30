"""
Main entry point for Clarity extensions in the SNP&SEQ installation
"""
from setuptools import find_packages, setup

# Add that to the dev reqs file for now, since it's not needed when running
dependencies = ['click', 'genologics', 'requests-cache', 'pyyaml', 'nose', 'PyPDF2',
                'lxml']

setup(
    name='clarity-ext',
    version='0.1.0',
    url='https://github.com/withrocks/clarity-ext',
    license='BSD',
    author='withrocks',
    author_email='withrocks',
    description='Main entry point for Clarity extensions in the SNP&SEQ installation',
    long_description=__doc__,
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=dependencies,
    entry_points={
        'console_scripts': [
            'clarity-ext = clarity_ext.cli:main',
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
