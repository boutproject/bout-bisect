from setuptools import setup

name = "bout_bisect"
version = "0.1.0"

setup(
    name=name,
    version=version,
    description="BOUT++ git bisect helper",
    author="Peter Hill",
    license="MIT",
    packages=["bout_bisect"],
    install_requires=["numpy >= 1.17.0", "pandas >= 0.24.2"],
    entry_points={"console_scripts": ["bout_bisect = bout_bisect.bout_bisect:main"]},
)
