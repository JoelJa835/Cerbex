from setuptools import setup, find_packages

setup(
    name="pylya",
    version="0.1.0",
    description="Pylya: Python hook instrumentation and enforcement tool",
    author="Your Name",
    packages=find_packages(),  # Automatically finds pylya/
    install_requires=[
        # Add your runtime deps here (if any)
    ],
    entry_points={
        "console_scripts": [
            "pylya=pylya.cli:main",  # CLI entry point
        ],
    },
    include_package_data=True,
    python_requires=">=3.7",
)
