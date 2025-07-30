from setuptools import setup, find_packages

setup(
    name="pylya",
    version="0.1.0",
    description="Pylya: Python hook instrumentation and enforcement tool",
    author="Joel Jani",
    packages=find_packages(),
    install_requires=[
        # add dependencies here
    ],
    entry_points={
        "console_scripts": [
            "pylya=cli:main",
        ],
    },
    include_package_data=True,
)