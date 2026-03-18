from setuptools import setup, find_packages

setup(
    name="supplyshock",
    version="0.1.0",
    description="Python SDK for the SupplyShock API",
    author="SupplyShock",
    url="https://github.com/supplyshock/supplyshock-python",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "httpx>=0.24.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
