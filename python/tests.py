import json
import os
from os.path import join,isfile,isdir
import re
import shutil
from spark_package.spark_package import licenses,register_package_http,check_homepage
import sys
if sys.version_info >= (3, 0):
    from io import StringIO
else:
    from StringIO import StringIO
import subprocess
import tempfile
import unittest
import zipfile
import responses
import pexpect

def run_cmd(cmd):
    return subprocess.Popen(["spark-package"] + cmd, stdout=subprocess.PIPE,
                            stdin=subprocess.PIPE, stderr=subprocess.PIPE, close_fds = True)


def spawn(cmd):
    return pexpect.spawn(" ".join(["spark-package"] + cmd))


def input_and_expect(p, vals):
    for prompt, input in vals:
        p.expect(re.compile(prompt))
        p.sendline(input)


def communicate(p, val):
    if type(val) is list:
        # stdo = [p.stdout.readline().decode("utf-8")]
        for input in val:
            p.stdin.write(input)
            p.stdin.flush()
            # stdo.append(p.stdout.readline().decode("utf-8"))
        return p.communicate()
    if sys.version_info >= (3, 0):
        return p.communicate(val.encode())
    else:
        return p.communicate(val)


def check_sbt_files(test, temp_dir, name, exists=True):
    base_name = name.split("/")[1]
    if exists:
        check_exists = test.assertTrue
    else:
        check_exists = test.assertFalse
    check_exists(isdir(join(temp_dir, base_name, "project")))
    check_exists(isfile(join(temp_dir, base_name, "project", "build.properties")))
    check_exists(isfile(join(temp_dir, base_name, "project", "plugins.sbt")))
    check_exists(isdir(join(temp_dir, base_name, "build")))
    check_exists(isfile(join(temp_dir, base_name, "build", "sbt")))
    check_exists(isfile(join(temp_dir, base_name, "build", "sbt-launch-lib.bash")))
    build_file = join(temp_dir, base_name, "build.sbt")
    check_exists(isfile(build_file))
    if exists:
        with open(build_file, 'r') as f:
            test.assertTrue("spName := \"%s\"" % name in f.read())


def check_scala_files(test, temp_dir, name, exists=True):
    base_name = name.split("/")[1]
    if exists:
        check_exists = test.assertTrue
    else:
        check_exists = test.assertFalse
    check_exists(isdir(join(temp_dir, base_name, "src", "main", "scala")))
    check_exists(isdir(join(temp_dir, base_name, "src", "test", "scala")))


def check_base_files(test, temp_dir, name):
    base_name = name.split("/")[1]
    test.assertTrue(isfile(join(temp_dir, base_name, "LICENSE")))
    test.assertTrue(isfile(join(temp_dir, base_name, "README.md")))
    test.assertTrue(isfile(join(temp_dir, base_name, ".gitignore")))


def check_python_files(test, temp_dir, name, exists=True):
    base_name = name.split("/")[1]
    if exists:
        check_exists = test.assertTrue
    else:
        check_exists = test.assertFalse
    check_exists(isdir(join(temp_dir, base_name, "python")))
    check_exists(isfile(join(temp_dir, base_name, "python", "setup.py")))
    check_exists(isfile(join(temp_dir, base_name, "python", "setup.cfg")))
    check_exists(isfile(join(temp_dir, base_name, "python", "MANIFEST.in")))
    check_exists(isfile(join(temp_dir, base_name, "python", "requirements.txt")))
    check_exists(isfile(join(temp_dir, base_name, "python", "spark-package-deps.txt")))
    check_exists(isfile(join(temp_dir, base_name, "python", "tests.py")))


def check_java_files(test, temp_dir, name, exists=True):
    base_name = name.split("/")[1]
    if exists:
        check_exists = test.assertTrue
    else:
        check_exists = test.assertFalse
    check_exists(isdir(join(temp_dir, base_name, "src", "main", "java")))
    check_exists(isdir(join(temp_dir, base_name, "src", "test", "java")))


def check_r_files(test, temp_dir, name, exists=True):
    base_name = name.split("/")[1]
    if exists:
        check_exists = test.assertTrue
    else:
        check_exists = test.assertFalse
    check_exists(isdir(join(temp_dir, base_name, "R", "pkg", "R")))
    check_exists(isdir(join(temp_dir, base_name, "R", "pkg", "man")))
    check_exists(isdir(join(temp_dir, base_name, "R", "pkg", "data")))
    check_exists(isdir(join(temp_dir, base_name, "R", "pkg", "src")))
    check_exists(isfile(join(temp_dir, base_name, "R", "pkg", "NAMESPACE")))
    check_exists(isfile(join(temp_dir, base_name, "R", "pkg", "man", "documentation.Rd")))
    check_exists(isfile(join(temp_dir, base_name, "R", "pkg", "Read-and-delete-me")))
    description = join(temp_dir, base_name, "R", "pkg", "DESCRIPTION")
    check_exists(isfile(description))
    if exists:
        with open(description, 'r') as f:
            test.assertTrue("Package: %s" % base_name in f.read())


def clean_dir(test, dir):
    shutil.rmtree(dir)
    test.assertFalse(isdir(dir))


def check_exception(test, expect, p):
    out, _ = p.communicate()
    test.assertTrue(expect in out.decode('utf-8'))


def get_licenses():
    first_lines = [
        "Apache License, Version 2.0",
        "Copyright (c) <YEAR>, <OWNER>",
        "Copyright (c) <YEAR>, <OWNER>",
        "The GNU General Public License (GPL-2.0)",
        "GNU GENERAL PUBLIC LICENSE",
        "GNU Lesser General Public License",
        "GNU LESSER GENERAL PUBLIC LICENSE",
        "The MIT License (MIT)",
        "Mozilla Public License, version 2.0",
        "Eclipse Public License, Version 1.0 (EPL-1.0)",
        "# Every Spark Package must have a license in order to be published. You may"
    ]
    return [(x[0], x[1], y) for x, y in zip(licenses, first_lines)]


class TestCommandLineToolInit(unittest.TestCase):

    def test_simple(self):
        p = run_cmd(["init"])
        check_exception(self, "Please specify the name of the package using -n or --name.", p)

    def test_bad_name(self):
        p = run_cmd(["init", "-n", "noslash"])
        check_exception(self, "The name of the package must contain exactly one slash.", p)
        p = run_cmd(["init", "-n", "abc/03/doubleslash"])
        check_exception(self, "The name of the package must contain exactly one slash.", p)
        p = run_cmd(["init", "-n", "w3!rd/ch@rs"])
        check_exception(self, "The name of the package can only contain letters, numbers,", p)

    def test_matrix(self):
        has_lang_opts = [True, False]
        i = 0
        for has_scala in has_lang_opts:
            for has_r in has_lang_opts:
                for has_python in has_lang_opts:
                    for has_java in has_lang_opts:
                        temp_dir = tempfile.mkdtemp()
                        name = "test/trial-%s" % i
                        langs = []
                        if has_java:
                            langs.append("-j")
                        if has_scala:
                            langs.append("-s")
                        if has_python:
                            langs.append("-p")
                        if has_r:
                            langs.append("-r")
                        if not has_java and not has_scala and not has_python and not has_r:
                            has_scala = True
                        p = run_cmd(["init", "-n", name, "-o", temp_dir] + langs)
                        communicate(p, "1")
                        self.assertTrue(p.returncode == 0)
                        check_scala_files(self, temp_dir, name, exists=has_scala)
                        check_base_files(self, temp_dir, name)
                        check_sbt_files(self, temp_dir, name, exists=has_scala | has_java)
                        check_python_files(self, temp_dir, name, exists=has_python)
                        check_r_files(self, temp_dir, name, exists=has_r)
                        check_java_files(self, temp_dir, name, exists=has_java)
                        clean_dir(self, temp_dir)
                        i += 1

    def test_license(self):
        i = 1
        for license_name, url, first_line in get_licenses():
            temp_dir = tempfile.mkdtemp()
            name = "license-%s" % i
            print("license-%s" % i)
            p = run_cmd(["init", "-n", "test/" + name, "-o", temp_dir])
            out, err = communicate(p, str(i))
            print(out)
            print(err)
            check_base_files(self, temp_dir, "test/" + name)
            if i != len(licenses):
                with open(join(temp_dir, name, "build.sbt"), "r") as f:
                    contents = f.read()
                    self.assertTrue(license_name in contents)
                    self.assertTrue(url in contents)
            with open(join(temp_dir, name, "LICENSE"), "r") as f:
                self.assertTrue(first_line in f.readline())
            i += 1
            clean_dir(self, temp_dir)


def check_pom(test, pom, org_name, artifact_name, version, dependencies):
    """
    Check the contents of the pom. Make sure the groupId, artifactId, and version are properly set.
    :param org_name: organization (group) id of the package
    :param artifact_name: artifact id of package
    :param version: version of release
    :param dependencies: List of dependencies expected in the pom
    """
    contents = pom.read()
    def gen_coordinate_regex(org, artifact, v):
        regex = """<groupId>\\s*%s\\s*<\\/groupId>\\s*""" % org
        regex += """<artifactId>\\s*%s\\s*<\\/artifactId>\\s*""" % artifact
        regex += """<version>\\s*%s\\s*<\\/version>""" % v
        return regex
    main = gen_coordinate_regex(org_name, artifact_name, version)
    test.assertTrue(len(re.findall(main, contents)) == 1)
    for dep_org, dep_art, dep_version in dependencies:
        dep = gen_coordinate_regex(dep_org, dep_art, dep_version)
        test.assertTrue(len(re.findall(dep, contents)) == 1)
    pom.close()

def check_jar(test, jar, files):
    """
    Check the contents of the pom. Make sure the groupId, artifactId, and version are properly set.
    :param files: List of entries expected in the jar
    """
    jar_file = zipfile.PyZipFile(StringIO(jar.read()), 'r')
    entries = jar_file.namelist()
    for expected in files:
        test.assertTrue(expected in entries)
    jar_file.close()
    jar.close()


def check_zip(test, temp_dir, org_name, artifact_name, version, files, dependencies):
    """
    Checks if the zip exists and the contents of the pom and jar are valid.
    :param temp_dir: Directory where the zip should exist
    :param org_name: organization (group) id of the package
    :param artifact_name: artifact id of package
    :param version: version of release
    :param files: List of entries expected in the jar
    :param dependencies: List of dependencies expected in the pom
    """
    artifact_format = "%s-%s" % (artifact_name, version)
    zip = join(temp_dir, artifact_format + ".zip" )
    test.assertTrue(isfile(zip))
    with zipfile.PyZipFile(zip, 'r') as myzip:
        entries = myzip.namelist()
        test.assertTrue(artifact_format + ".pom" in entries)
        test.assertTrue(artifact_format + ".jar" in entries)
        check_jar(test, myzip.open(artifact_format + ".jar"), files)
        check_pom(test, myzip.open(artifact_format + ".pom"),
                  org_name, artifact_name, version, dependencies)


def write_file(path, contents):
    with open(path, 'w') as f:
        f.write(contents)


def create_jar(temp_dir, artifact_name, version, files):
    jar = zipfile.PyZipFile(join(temp_dir, artifact_name,
                                 "%s-%s.jar" % (artifact_name, version)), 'w')
    for f in files:
        jar.write(f, f.replace(temp_dir, ""))
    jar.close()


def create_pom(temp_dir, group_id, artifact_id, version):
    contents = ("""
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>%s</groupId>
    <artifactId>%s</artifactId>
    <version>%s</version>
</project>""" % (group_id, artifact_id, version)).strip()
    write_file(join(temp_dir, "pom.xml"), contents)


class TestCommandLineToolZip(unittest.TestCase):

    def test_zip_missing_args(self):
        temp_dir = tempfile.mkdtemp()
        name = "test/zip-test"
        p = run_cmd(["init", "-n", name, "-o", temp_dir])
        communicate(p, "1")
        p = run_cmd(["zip"])
        check_exception(self, "Please specify the name of the package using -n or --name", p)
        p = run_cmd(["zip", "-n", name])
        check_exception(self, "Please specify the folder of the spark package", p)
        p = run_cmd(["zip", "-n", name, "-f", join(temp_dir, "zip-test")])
        check_exception(self, "Please specify a version for the release", p)
        clean_dir(self, temp_dir)

    def test_zip_bad_names(self):
        p = run_cmd(["zip", "-n", "noslash"])
        check_exception(self, "The name of the package must contain exactly one slash.", p)
        p = run_cmd(["zip", "-n", "abc/03/doubleslash"])
        check_exception(self, "The name of the package must contain exactly one slash.", p)
        p = run_cmd(["zip", "-n", "w3!rd/ch@rs"])
        check_exception(self, "The name of the package can only contain letters, numbers,", p)

    def test_zip_proper(self):
        temp_dir = tempfile.mkdtemp()
        org_name = "test"
        base_name = "zip-test"
        name = org_name + "/" + base_name
        p = run_cmd(["init", "-n", name, "-o", temp_dir, "-p"])
        communicate(p, "1")
        version = "0.2"
        p = run_cmd(["zip", "-n", name, "-o", temp_dir, "-v", version,
                     "-f", join(temp_dir, base_name)])
        p.wait()
        jar_contents = ["setup.pyc", "requirements.txt", "tests.pyc"]
        check_zip(self, temp_dir, org_name, base_name, version, files=jar_contents, dependencies=[])
        clean_dir(self, temp_dir)

    def test_zip_existing_jar(self):
        temp_dir = tempfile.mkdtemp()
        org_name = "test"
        base_name = "zip-test"
        name = org_name + "/" + base_name
        p = run_cmd(["init", "-n", name, "-o", temp_dir, "-p", "-s"])
        communicate(p, "1")
        version = "0.2"
        test1 = join(temp_dir, "test.class")
        test2 = join(temp_dir, "test2.class")
        write_file(join(temp_dir, "test.class"), "hulahulahulahey")
        write_file(join(temp_dir, "test2.class"), "hulahulahulaheyheyhey")
        create_jar(temp_dir, base_name, version, [test1, test2])
        self.assertTrue(isfile(join(temp_dir, base_name, "%s-%s.jar" % (base_name, version))))
        create_pom(join(temp_dir, base_name), "org.test", base_name, version)
        self.assertTrue(isfile(join(temp_dir, base_name, "pom.xml")))
        p = run_cmd(["zip", "-n", name, "-o", temp_dir, "-v", version,
                     "-f", join(temp_dir, base_name)])
        p.wait()
        jar_contents = ["setup.pyc", "requirements.txt", "tests.pyc", "test.class", "test2.class"]
        check_zip(self, temp_dir, org_name, base_name, version, files=jar_contents, dependencies=[])
        clean_dir(self, temp_dir)

    def test_zip_python_dependencies(self):
        temp_dir = tempfile.mkdtemp()
        org_name = "test"
        base_name = "zip-test"
        name = org_name + "/" + base_name
        p = run_cmd(["init", "-n", name, "-o", temp_dir, "-p"])
        communicate(p, "1")
        version = "0.2"
        deps_file = join(temp_dir, base_name, "python", "spark-package-deps.txt")
        write_file(deps_file, """wrong/format\n""")
        p = run_cmd(["zip", "-n", name, "-o", temp_dir, "-v", version,
                     "-f", join(temp_dir, base_name)])
        check_exception(self, ":package_name==:version` in spark-package-deps.txt", p)
        write_file(deps_file, """wrong:format==2\n""")
        p = run_cmd(["zip", "-n", name, "-o", temp_dir, "-v", version,
                     "-f", join(temp_dir, base_name)])
        check_exception(self, "supplied as: `:repo_owner_name/:repo_name` in", p)

        write_file(deps_file, """right/format==3\n""")
        p = run_cmd(["zip", "-n", name, "-o", temp_dir, "-v", version,
                     "-f", join(temp_dir, base_name)])
        p.wait()
        jar_contents = ["setup.pyc", "requirements.txt", "tests.pyc"]
        check_zip(self, temp_dir, org_name, base_name, version,
                  files=jar_contents, dependencies=[("right", "format", "3")])
        clean_dir(self, temp_dir)


class TestCommandLineToolRegister(unittest.TestCase):

    def test_register_bad_args(self):
        p = run_cmd(["register"])
        check_exception(self, "Please specify the name of the package using -n or --name", p)

    def test_ask_git_creds(self):
        p = spawn(["register", "-n", "test/register"])
        input_and_expect(p, [
            ("Please enter your Github username.*", "git-user"),
            ("Github Personal access token with read\:org.*", "git-password")])
        p.expect(re.compile("Please supply a short \(one line\) description of.*"))
        p.kill(0)

    @responses.activate
    def test_simple_register(self):
        responses.add(
            responses.POST, 'http://spark-packages.org/api/submit-package',
            body="",
            status=201)
        register_package_http("test/register", "fake", "token", "short", "long", "http://homepage")
        self.assertTrue(len(responses.calls) == 1)
        self.assertTrue(responses.calls[0].request.url ==
                        'http://spark-packages.org/api/submit-package')



if __name__ == '__main__':
    unittest.main()
