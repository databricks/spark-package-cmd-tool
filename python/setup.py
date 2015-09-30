from setuptools import setup
from os import listdir, path

resource_files = listdir(path.join('spark_package', 'resources'))
resource_files = [f for f in resource_files if not path.isdir(f) and 'license_temps' not in f]

setup(
    name='spark-package',
    version="0.4.0",
    description="A command line tool for creating Spark Packages and " \
        "generating release distributions",
    author='Burak Yavuz',
    author_email='feedback@spark-packages.org',
    url='https://github.com/databricks/spark-package-cmd-tool',
    license="Apache-2.0",
    packages=['spark_package', 'spark_package.resources', 'spark_package.resources.license_temps'],
    package_data={"spark_package.resources": resource_files,
                  'spark_package.resources.license_temps': listdir(path.join('spark_package', 'resources', 'license_temps'))},
    entry_points = {'console_scripts': ['spark-package=spark_package.spark_package:main']},
    long_description=open('README.rst').read()
)
