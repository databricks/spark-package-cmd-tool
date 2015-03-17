spark-package Command Line Tool
===============================

Command Line Tool for working with `Spark Packages`_

.. _Spark Packages: http://spark-packages.org

Usage
-----

The `spark-package` command line tool is your helper when developing new `Spark Packages`.

The tool provides two methods: `init` and `zip`. Use `spark-package -h` to see the list of available
commands and options.

init
----

Initializes an empty project. Sets up the recommended directory layout and provides templates for
required files. The tool will prompt the user to select a license, but users may skip this process 
by selecting the value for `other license (decide later)`. 

A name must be supplied with the flag `-n` or `--name`. The name must match the name of the github 
repository of the package. The layout for python can be generated with the flag `-p` or `--python`, 
scala can be generated with `-s` or `--scala` and java folders can be generated with `-j` or `--java`. 
An output directory for the package can be supplied with `-o` or `--out`. The default for the output 
path is the current working directory.
Example usage:
 
Generate a folder called "package" in the current directory setup with all files regarding to scala.

```
spark-package init -n "test/package"
```

Generate a folder called "package" in $PACKAGE_PATH setup with all files regarding to scala and python.

```
spark-package init -s -p -n "test/package" -o $PACKAGE_PATH
```

zip
---

Creates a zip file for distribution on the Spark Packages website. If your package has java or 
scala code, use the `sbt-spark-package` plugin as it is more advanced. If your package is comprised 
of just python code, use this command.

The package name must be supplied with `-n` or `--name`. In addition, the root directory of the 
package must be supplied with `-f` or `--folder`. In addition, users must supply the version of the 
release they want to distribute with the flag `-v` or `--version`. The output directory of the 
zip file can be configured through `-o` or `--out`. The default path is the current working directory.

Example Usage:

Generate a zip file for distribution on the Spark Packages website with release version 0.2.1.

```
spark-package zip -f $PACKAGE_PATH -n "test/package" -v "0.2.1"
```

register
--------

Register your package on the Spark Packages website. Requires that you login to the Spark Packages
website at least once. In addition, a Github Personal Access Token with "read:org" permissions must be
supplied as a password. The credentials can be supplied through a file using `-c` or `--cred`. The 
format of the file must be:

```
user= $USERNAME
password= $TOKEN
```

*Note: If there are multiple user, passwords, the last ones in the file will be used*

For more information on Github Personal Access Tokens, please read the `Github documentation`_.

.. _Github documentation: http://help.github.com/articles/creating-an-access-token-for-command-line-use/

Then you will be asked to enter a short description of your package, a long description, and the
homepage of your package, which is by default the github repository of the package. The descriptions 
can be provided through files. Simply provide the relative path to the file once you are prompted.

Example usage:
```
spark-package register -c $CREDS_FILE -n "test/package"
# or
spark-package register -u $GITHUB_USERNAME -p $GITHUB_PASSWORD -n "test/package"
```

publish
-------

Publishes a new release on the Spark packages website. Like the `register` command, requires credentials (see above).
Requires either the path to the package with `-f` or the zip archive of the release artifact with `-z`.

Example usage:
```
spark-package publish -c $CREDS_FILE -f PACKAGE_PATH -n "test/package" -v "0.2.1"
# or
spark-package publish -c $CREDS_FILE -z $ZIP_FILE -n "test/package" -v "0.2.1"
```

Contributions
-------------
If you encounter bugs or want to contribute, feel free to submit an issue or pull request.

