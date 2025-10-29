from setuptools import setup, find_packages

setup(
    name="Cerbex",
    version="0.1.0",
    description="Cerbex: Python hook instrumentation and enforcement tool",
    author="Joel Jani",
    packages=find_packages(),  # Automatically finds Cerbex/
    install_requires=[
        # Add your runtime deps here (if any)
    ],
    entry_points={
        "console_scripts": [
            "Cerbex=Cerbex.cli:main",  # CLI entry point
        ],
    },
    include_package_data=True,
    python_requires=">=3.7",
)
