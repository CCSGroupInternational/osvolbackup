from setuptools import setup, find_packages

all_packages = find_packages()

setup(
    name="osvolbackup",
    packages=all_packages,
    entry_points={
        'console_scripts': [
            'osvolbackup = osvolbackup.__main__:main'
        ]
    }
)
