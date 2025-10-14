from setuptools import setup, find_packages

setup(
    name="mkdocs-multiline-abbr",
    version="0.1",
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        "mkdocs.plugins": [
            "multiline_abbr = multiline_abbr.plugin:MultilineAbbrPlugin"
        ]
    },
)