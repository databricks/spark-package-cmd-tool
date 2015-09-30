#!/usr/bin/env python

"""
This command line tool aims to provide users a clean interface to help them in developing new
Spark Packages. Major functionalities provided by this tool:
 - init Set up an empty project with the standard template
 - zip Prepares the package for a release by creating a zip archive that includes the pom and
    jar of this package. A package jar must exist in the directory of the spark package
"""

import datetime
import optparse
import os
import re
import zipfile
import fnmatch
import xml.etree.ElementTree as Xml
import xml.dom.minidom as dom
import tempfile
import shutil
import base64
import requests
import subprocess
import sys
if sys.version_info >= (3, 0):
    from io import StringIO
else:
    from StringIO import StringIO
from getpass import getpass
from pkg_resources import resource_string
from builtins import input

# <----- zip Methods ------>

def validate_files_exist(root_dir):
    """
    Checks if the required files (LICENSE, README, pom) exist
    """
    files = os.listdir(root_dir)
    if 'README.md' not in files:
        show_error_and_exit('Cannot find README.md in the root directory of the package.')
    if not get_license_file_name(root_dir):
        show_error_and_exit('Cannot find LICENSE in the root directory of the package.')


def prepare_pom(root_dir, name, version, out_dir):
    """
    Writes the pom file using the existing pom (if one exists) in the root directory.
    Changes are made to the groupId, artifactId, and version as necessary. Also, if python has
    spark-package-deps.txt, those are added to the pom as well.
    """
    group_id, artifact_id = name.strip().split("/")
    # In case people want to use their own pom.xml. sbt-spark-package plugin does everything that
    # zip does in this tool. This is useful for purely python packages.
    existing_pom_path = os.path.join(root_dir, 'pom.xml')
    if os.path.isfile(existing_pom_path):
        Xml.register_namespace('', "http://maven.apache.org/POM/4.0.0")
        old_pom = Xml.parse(existing_pom_path)
        project = old_pom.getroot()
        # The XML parser returns a prefix {http://maven.apache.org/POM/4.0.0} to all nodes. The
        # following code gets that prefix, rather than hard-coding it, in case there isn't one.
        prefix_length = project.tag.find('project')
        assert prefix_length > -1, \
            "The root node of the pom file should be <project>, not: %s" % project.tag
        prefix = project.tag[:prefix_length]
    else:
        # Write a pom file from scratch
        attributes = {
            "xmlns": "http://maven.apache.org/POM/4.0.0",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xsi:schemaLocation": "http://maven.apache.org/POM/4.0.0 "
                                  "http://maven.apache.org/xsd/maven-4.0.0.xsd"
        }
        project = Xml.Element('project', attributes)
        prefix = ""
    # modify groupId to the github repo owner
    pom_add_or_modify_tag(project, prefix + 'groupId', group_id, 1)
    # modify artifactId to the github repo name
    pom_add_or_modify_tag(project, prefix + 'artifactId', artifact_id, 2)
    # modify version to the release version supplied as argument
    pom_add_or_modify_tag(project, prefix + 'version', version, 3)
    # if the project has spark-package dependencies in python (spark-package-deps.txt), add them to
    # the pom
    sp_deps_path = os.path.join(root_dir, 'python', 'spark-package-deps.txt')
    if os.path.isfile(sp_deps_path):
        sp_deps = open(sp_deps_path, 'r')
        for line in sp_deps.readlines():
            line = line.strip()
            if not line.startswith('#'):
                dep_group_id, dep_artifact_id, dep_version = validate_and_return_sp_dep(line)
                dep = {"groupId": dep_group_id,
                       "artifactId": dep_artifact_id,
                       "version": dep_version}
                keys = ["groupId", "artifactId"] # keys to compare on
                pom_add_element(project, prefix, "dependencies", "dependency", dep, keys,
                                ["groupId", "artifactId", "version"])
    repo = {"id": "SparkPackagesRepo",
           "name": "Spark Packages Repository",
           "url": "http://dl.bintray.com/spark-packages/maven/",
           "layout": "default"}
    pom_add_element(project, prefix, "repositories", "repository", repo, ["url"],
                    ["id", "name", "url", "layout"])
    with open(os.path.join(out_dir, "%s-%s.pom" % (artifact_id, version)), 'w') as new_pom:
        new_pom.write(pom_pretty_print(Xml.tostring(project, encoding='UTF-8')))


def prepare_jar(root_dir, artifact_name):
    """
    Zips compiled java, scala and python files in a jar. Python files are added to the root
    directory, because that's how python can find those files. Only class files, LICENSE, README,
    and POM are added
    """
    pwd = os.getcwd()
    # A PyZipFile will package python binaries for us
    jar = zipfile.PyZipFile(artifact_name + "jar", 'w')
    os.chdir(root_dir)
    files = os.listdir('.')
    if os.path.isdir(os.path.join('src', 'main', 'scala')) or \
        os.path.isdir(os.path.join('src', 'main', 'java')):
        # Find the jar that was built, if there are any scala or java files.
        # Will omit any jars in lib/
        existing_jars = []
        for root, dirnames, filenames in os.walk('.'):
            for filename in fnmatch.filter(filenames, '*.jar'):
                if 'lib' not in filename and 'sbt' not in filename and 'assembly' not in filename:
                    existing_jars.append(os.path.join(root, filename))
        if len(existing_jars) == 0:
            show_error_and_exit("Your directory contains java or scala code but a jar could not "
                                "be found. Please build your spark package before calling zip."
                                "\nIf the jar is in a directory like lib/, zip omits those jars. "
                                "Please move your jar elsewhere to use zip properly.")
        elif len(existing_jars) > 1:
            show_error_and_exit("Your directory contains multiple jars. We only need your "
                                "package jar, not the assembly jar, nor any jars that your package"
                                " depends on."
                                "\nIf there are dependency jars in your folder, please place them "
                                "under lib/ and add them to your pom or sbt build file.")
        old_jar = zipfile.ZipFile(existing_jars[0])
        for f in old_jar.namelist():
            old_jar_content = old_jar.open(f, 'r')
            jar.writestr(f, old_jar_content.read())
            old_jar_content.close()
    jar.write(get_license_file_name('.'))
    jar.write('README.md')
    if 'python' in files:
        os.chdir(os.path.join('.', 'python'))
        jar.writepy('.')
        if os.path.isfile('requirements.txt'):
            jar.write('requirements.txt')
        python_dirs = [ p for p in os.listdir('.') if os.path.isdir(p) and 'bin' not in p
                        and 'doc' not in p and '.git' not in p and 'lib' not in p ]
        for dir in python_dirs:
            jar.writepy(dir)
    jar.close()
    os.chdir(pwd)


def zip_artifact(root_dir, name, version, out_dir):
    """
    Creates a zip artifact containing a jar file and a pom file for the package
    """
    validate_name(name)
    validate_files_exist(root_dir)
    temp_dir = tempfile.mkdtemp(dir=out_dir)
    artifact_name = "%s-%s." % (name.split('/')[1], version)
    temp_artifact_name = os.path.join(temp_dir, artifact_name)
    prepare_jar(root_dir, temp_artifact_name)
    prepare_pom(root_dir, name, version, temp_dir)
    pwd = os.getcwd()
    zip_path = os.path.join(out_dir, artifact_name + "zip")
    artifact = zipfile.ZipFile(zip_path, 'w')
    os.chdir(temp_dir)
    artifact.write(artifact_name + "pom")
    artifact.write(artifact_name + "jar")
    artifact.close()
    os.chdir(pwd)
    shutil.rmtree(temp_dir)
    print("Zip File created at: %s" % os.path.abspath(zip_path))
    return zip_path


# <----- init Methods ------>

licenses = [
    ('Apache-2.0', 'http://opensource.org/licenses/Apache-2.0'),
    ('BSD 3-Clause', 'http://opensource.org/licenses/BSD-3-Clause'),
    ('BSD 2-Clause', 'http://opensource.org/licenses/BSD-2-Clause'),
    ('GPL-2.0', 'http://opensource.org/licenses/GPL-2.0'),
    ('GPL-3.0', 'http://opensource.org/licenses/GPL-3.0'),
    ('LGPL-2.1', 'http://opensource.org/licenses/LGPL-2.1'),
    ('LGPL-3.0', 'http://opensource.org/licenses/LGPL-3.0'),
    ('MIT', 'http://opensource.org/licenses/MIT'),
    ('MPL-2.0', 'http://opensource.org/licenses/MPL-2.0'),
    ('EPL-1.0', 'http://opensource.org/licenses/EPL-1.0'),
    ('other license (decide later)', 'n/a')]


def get_license_prompt():
    msg = "Please select a license for your package (enter index):\n"
    license_list = ["%d.\t%s\t\turl: %s" % (i + 1, l[0], l[1]) for i, l in enumerate(licenses)]
    return msg + '\n'.join(license_list) + "\n"


def create_license_file(license_id):
    file = 'LICENSE'
    if license_id == len(licenses):
        res_file = resource_string('spark_package.resources', 'LICENSE').decode("utf-8")
    else:
        res_file = resource_string('spark_package.resources.license_temps',
                                   licenses[license_id - 1][0]).decode("utf-8")
    f = open(file, 'w')
    f.write(res_file)
    f.close()


def init_src_directories(suffix):
    os.makedirs(os.path.join("src", "main", suffix))
    os.makedirs(os.path.join("src", "test", suffix))


def get_license_replacement(license_id, just_name=False):
    if license_id != len(licenses):
        license_name, license_url = licenses[license_id - 1]
        if just_name:
            return "$$license$$", license_name
        return ("$$license$$",
                "licenses := Seq(\"%s\" -> url(\"%s\"))\n" % (license_name, license_url))
    else:
        if just_name:
            return "$$license$$", "Please specify a license"
        return "$$license$$", "// format: licenses := Seq($LICENSE_NAME -> $LICENSE_URL)"



def init_sbt_directories(name, license_id):
    os.makedirs("project")
    build_replacements = [("$$packageName$$", name), get_license_replacement(license_id)]
    create_static_file("build.sbt", replacements=build_replacements)
    create_static_file(os.path.join("project", "build.properties"))
    create_static_file(os.path.join("project", "plugins.sbt"))
    os.makedirs("build")
    create_static_file(os.path.join("build", "sbt"), 0o777)
    create_static_file(os.path.join("build", "sbt-launch-lib.bash"), 0o777)


def init_python_directories():
    os.makedirs("python")
    create_static_file(os.path.join("python", "setup.py"))
    create_static_file(os.path.join("python", "setup.cfg"))
    create_static_file(os.path.join("python", "MANIFEST.in"))
    create_static_file(os.path.join("python", "requirements.txt"))
    create_static_file(os.path.join("python", "spark-package-deps.txt"))
    create_static_file(os.path.join("python", "tests.py"))


def init_r_directories(name, license_id):
    os.makedirs(os.path.join("R", "pkg", "R"))
    os.makedirs(os.path.join("R", "pkg", "man"))
    os.makedirs(os.path.join("R", "pkg", "data"))
    os.makedirs(os.path.join("R", "pkg", "src"))
    replacements = [("$$packageName$$", name.split("/")[1]),
                    ("$$date$$", datetime.datetime.now().strftime("%Y-%m-%d")),
                    get_license_replacement(license_id, just_name=True)]
    create_static_file(os.path.join("R", "pkg", "DESCRIPTION"), replacements=replacements)
    create_static_file(os.path.join("R", "pkg", "NAMESPACE"))
    create_static_file(os.path.join("R", "pkg", "man", "documentation.Rd"),
                       replacements=replacements)
    create_static_file(os.path.join("R", "pkg", "Read-and-delete-me"))


def init_empty_package(base_dir, name, scala, java, python, r):
    repo_name = name.split("/")[1]
    package_dir = os.path.join(base_dir, repo_name)
    if os.path.exists(package_dir):
        raise RuntimeError("Directory %s already exists" % package_dir)
    license_id = get_license_id()
    os.makedirs(package_dir)
    os.chdir(package_dir)
    create_license_file(license_id)
    create_static_file('README.md')
    create_static_file('.gitignore')
    if not scala and not java:
        if python:
            init_python_directories()
        if r:
            init_r_directories(name, license_id)
    else:
        init_src_directories("resources")
        if java or scala:
            init_sbt_directories(name, license_id)
        if java:
            init_src_directories("java")
        if scala:
            init_src_directories("scala")
        if python:
            init_python_directories()
        if r:
            init_r_directories(name, license_id)


# <----- register Methods ------>

def get_description(desc_prompt):
    desc_raw = input(desc_prompt).strip()
    if desc_raw == "":
        show_error_and_exit("Please supply a proper description or the path to a file:\n")
    if os.path.isfile(desc_raw):
        with open(desc_raw) as f:
            desc = f.read()
        assert len(desc.strip()) > 0, "The file you submitted is empty. Please supply a " \
                                      "description of your package:\n"
    else:
        desc = desc_raw
    return desc


def check_homepage(homepage):
    """
    Check if homepage exists, because users can't update a wrong link on the Spark Packages website.
    """
    resp = requests.get(homepage)
    resp.raise_for_status()


def register_package_http(name, user, token, short_desc, long_desc, homepage):
    url = "http://spark-packages.org/api/submit-package"
    params = {"name": name,
              "homepage": homepage,
              "short_description": short_desc,
              "description": long_desc}
    auth = base64.b64encode((user + ":" + token).encode())
    h = {"Authorization": "Basic " + auth.decode("utf-8")}
    return requests.post(url, headers=h, data=params)


def register_package(name, user, token):
    homepage = "https://github.com/" + name
    short_desc = get_description("Please supply a short (one line) description of your package." + \
                                 " You may also provide a file containing the short description:\n")
    long_desc = get_description("Please supply a long description of your package." + \
                                 " You may also provide a file containing the long description:\n")
    new_hpg = input("Homepage of your package (%s): " % homepage)
    if len(new_hpg.strip()) > 0:
        homepage = new_hpg
    check_homepage(homepage)
    resp = register_package_http(name, user, token, short_desc, long_desc, homepage)
    if resp.status_code == 201:
        print("\nSUCCESS: %s" % resp.text)
    else:
        print("\nERROR: %s" % resp.text)


# <----- publish Methods ------>

def publish_release(name, user, token, folder, version, out, zip):
    auth = base64.b64encode((user + ":" + token).encode())
    pwd = os.getcwd()
    os.chdir(folder)
    p = subprocess.Popen(["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE)
    sys_out, sys_err = p.communicate()
    assert sys_out is not None, \
        "Problem while accessing git commit sha. Is the folder also the local github repository?"
    assert len(sys_out.strip()) != 0, \
        "Problem while accessing git commit sha. Is the folder also the local github repository?"
    git_sha1 = sys_out.strip()
    # -1 because prompt is one based, whereas the website is zero based.
    license_id = get_license_id() - 1
    os.chdir(pwd)
    if zip is None:
        zip = zip_artifact(folder, name, version, out)
    binary_zip = ""
    if zip is not None:
        with open(zip, 'rb') as f:
            binary_zip = base64.b64encode(f.read())
    artifact_zip = StringIO(binary_zip.decode("utf-8"))
    url = "http://spark-packages.org/api/submit-release"
    params = {"git_commit_sha1": git_sha1,
              "version": version,
              "license_id": license_id,
              "name": name}
    f = {"artifact_zip": artifact_zip}
    h = {"Authorization": "Basic " + auth.decode("utf-8")}
    resp = requests.post(url, headers=h, data=params, files=f)
    if resp.status_code == 201:
        print("\nSUCCESS: %s" % resp.text)
    else:
        print("\nERROR: %s" % resp.text)

# <----- util Methods ------>

def get_license_id():
    license_id = int(input(get_license_prompt()))
    while license_id < 1 or license_id > len(licenses):
        print("Please enter a value between 1-%d" % len(licenses))
        license_id = int(input(get_license_prompt()))
    return license_id

def get_license_file_name(root_dir):
    files = os.listdir(root_dir)
    if 'LICENSE' in files:
        return 'LICENSE'
    if 'LICENSE.txt' in files:
        return 'LICENSE.txt'
    if 'LICENSE.md' in files:
        return 'LICENSE.md'
    return None


def show_error_and_exit(msg, parser=None):
    print(msg)
    if parser is not None:
        parser.print_help()
    exit(-1)


name_template = """
The name consists of two parts: :org_name/:repo_name.
It is required that this name be the name of the
github repository of this package."""


def validate_name(name, p=None):
    """
    Makes sure that the package name doesn't contain any characters outside of letters and numbers
    """
    if name is None or len(name.strip()) == 0:
        show_error_and_exit("Please specify the name of the package using -n or --name." +
                            name_template, p)
    fields = name.split("/")
    if len(fields) != 2:
        show_error_and_exit("The name of the package must contain exactly one slash." +
                            name_template)
    for n in fields:
        if not re.match('^[a-zA-Z0-9-_]*$', n):
            show_error_and_exit("The name of the package can only contain letters, numbers, "
                                "dashes, underscores, and must contain a single slash." +
                                name_template)


def validate_and_return_sp_dep(line):
    first_split = line.split("==")
    if len(first_split) != 2:
        show_error_and_exit("Spark Package dependencies must be supplied as: "
                            "`:package_name==:version` in spark-package-deps.txt. Found: %s" % line)
    package_name = first_split[0]
    version = first_split[1]
    second_split = package_name.split("/")
    if len(second_split) != 2:
        show_error_and_exit("Spark Package names must be supplied as: `:repo_owner_name/"
                            ":repo_name` in spark-package-deps.txt. Found: %s" % package_name)
    return second_split[0], second_split[1], version


def pom_pretty_print(f):
    return dom.parseString(f).toprettyxml(indent=' ' * 2, encoding='UTF-8')\
        .decode("utf-8").strip('\n')


def pom_check_if_child_exists(parent, prefix, values, comparison_tags):
    for child in parent:
        match = 0
        for tag in comparison_tags:
            key = child.find(prefix + tag)
            if key.text == values[tag]:
                match += 1
        if match == len(comparison_tags):
            return True
    return False


def pom_add_or_modify_tag(root, tag, text, insert_index=None):
    """
    Modifies the value of the given child, or adds the child if it doesn't exist
    """
    child = root.find(tag)
    if child is None:
        child = Xml.Element(tag)
        if insert_index is None:
            root.append(child)
        else:
            root.insert(insert_index, child)
    child.text = text


def pom_add_element(root, prefix, parent, child, values, comparison_keys, key_order):
    """
    Checks if an element (spark-package dependency or repository) exists, adds it if it doesn't.
    'values' is a dictionary. 'comparison_keys' is a list of keys to compare on.
    """
    dependencies = root.find(prefix + parent)
    if dependencies is None:
        dependencies = Xml.Element(prefix + parent)
        root.append(dependencies)
    if not pom_check_if_child_exists(dependencies, prefix, values, comparison_keys):
        dep = Xml.Element(prefix + child)
        for key, value in sorted(values.items(), key=lambda i:key_order.index(i[0])):
            pom_add_or_modify_tag(dep, prefix + key, value)
        dependencies.append(dep)


def read_credentials_file(file):
    user = ""
    token = ""
    with open(file, 'r') as f:
        content = [x.strip('\n') for x in f.readlines()]
        for line in content:
            if 'user=' in line:
                str_line = line.strip()
                user = str_line[len('user='):].strip()
            elif 'password=' in line:
                str_line = line.strip()
                token = str_line[len('password='):].strip()
    if user == "":
        show_error_and_exit("Could not resolve github username from the file: %s. Please make " \
                            "sure that it's supplied in its own line as,\nuser= $USERNAME" % file)
    if token == "":
        show_error_and_exit("Could not resolve github token from the file: %s. Please make " \
                            "sure that it's supplied in its own line as,\npassword= $TOKEN" % file)
    return user, token


def resolve_credentials(user, token, file):
    if file is not None:
        if os.path.isfile(file):
            return read_credentials_file(file)
    if user is None or len(user.strip()) == 0:
        git_user = input("Please enter your Github username: ").strip()
    else:
        git_user = user
    if git_user == "":
        show_error_and_exit("Empty username provided!")
    if token is None or len(token.strip()) == 0:
        git_token = getpass("Please enter your Github Personal access token with read:org " + \
                            "permissions: ").strip()
    else:
        git_token = token
    if git_token == "":
        show_error_and_exit("Empty token provided!")
    return git_user, git_token


def create_static_file(file, permission=None, replacements=None):
    """
    Copies the static resource file to the newly created project.
    """
    if os.path.sep in file:
        file_name = file[file.rfind(os.path.sep):]
    else:
        file_name = file
    res_file = resource_string('spark_package.resources', file_name).decode("utf-8")
    if replacements is not None:
        for placeholder, value in replacements:
            res_file = res_file.replace(placeholder, value)
    f = open(file, 'w')
    f.write(res_file)
    f.close()
    if permission is not None:
        os.chmod(file, permission)


def check_path_exists(option):
    if option is None or len(option.strip()) == 0 or not os.path.isdir(option):
        return False
    return True


# <----- Main ------>

def main():
    # Set up and parse command line options
    usage = "usage: %prog <init|zip|register|publish> [options]"
    p = optparse.OptionParser(usage=usage)
    p.add_option("--out", "-o", type="string", default=".", help="The output directory for the "
                                                                 "package")
    p.add_option("--name", "-n", type="string", help="The name of the package. " + name_template)
    p.add_option("--version", "-v", type="string", help="The version of the release, when using " +\
                 "zip or publish.")
    p.add_option("--folder", "-f", type="string",
                 help="The root folder of the package that will be prepped for release")
    # Options for init
    init_options = optparse.OptionGroup(
        p, "'init' specific options", "Use these options when you want to set up an empty project "
                                      "with the standard template. You must supply a name when "
                                      "using init.")
    init_options.add_option(
        "--scala", "-s", action="store_true", default=False,
        help="Include this if your package uses/will use scala code. If none of the language flags"
             " are used, the package will be created using the scala template by default.")
    init_options.add_option(
        "--java", "-j", action="store_true", default=False,
        help="Include this if your package uses/will use java code")
    init_options.add_option(
        "--python", "-p", action="store_true", default=False,
        help="Include this if your package has/will have python code")
    init_options.add_option(
        "--R", "-r", action="store_true", default=False, dest="r",
        help="Include this if your package has/will have R code")
    p.add_option_group(init_options)
    # Credentials for register and publish
    credentials_options = optparse.OptionGroup(
        p, "credentials",
        "Set these options when you want to register your package or publish a release on " + \
        "Spark Packages. If credentials are not supplied beforehand, you will be prompted to " + \
        "enter them.")
    credentials_options.add_option(
        "--user", "-u", type="string", help="Your github username. It is safer to provide this " \
                                            "through a file using -c or --cred.")
    credentials_options.add_option(
        "--token", "-t", type="string",
        help="Your github personal access token with read:org authorization. It " + \
        "is safer to provide this through a file using -c or --cred.")
    credentials_options.add_option(
        "--cred", "-c", type="string",
        help="A file containing your github credentials, i.e. your username and personal access " \
             "token with read:org authorization. The format should be:" \
             "\nuser= $USERNAME\npassword= $TOKEN")
    p.add_option_group(credentials_options)
    # Register options
    register_options = optparse.OptionGroup(
        p, "register",
        "Register your package on Spark Packages. Requires that your package exist as a Github " + \
        "repository. If credentials are not supplied through command line arguments, you will be " + \
        "asked to enter them. Example usage: spark-package register -n $PACKAGE_NAME -c $CREDS_FILE.")
    p.add_option_group(register_options)
    # Options for publish
    publish_options = optparse.OptionGroup(
        p, "'publish' specific options",
        "Set these options when you want to publish a release on Spark Packages. Example " + \
        "usage: spark-package publish -c $CREDS_FILE -n $PACKAGE_NAME -f $PACKAGE_PATH -v $VERSION")
    publish_options.add_option(
        "--zip", "-z", type="string",
        help="The zip file containing the release artifact, if it has been generated beforehand.")
    p.add_option_group(publish_options)
    options, arguments = p.parse_args()
    if len(arguments) == 0:
        show_error_and_exit("Please specify an action, such as 'init', 'zip', 'register' or " + \
                            "'publish'", p)
    if len(arguments) > 1:
        show_error_and_exit("Unrecognized arguments", p)
    validate_name(options.name, p)
    if arguments[0] == "init":
        if not options.scala and not options.java and not options.python and not options.r:
            options.scala = True
        init_empty_package(options.out, options.name,
                           options.scala, options.java, options.python, options.r)
    elif arguments[0] == "zip":
        if not check_path_exists(options.folder):
            show_error_and_exit("Please specify the folder of the spark package", p)
        if options.version is None or len(options.version.strip()) == 0:
            show_error_and_exit("Please specify a version for the release", p)
        zip_artifact(options.folder, options.name, options.version, options.out)
    elif arguments[0] == "register":
        user, token = resolve_credentials(options.user, options.token, options.cred)
        register_package(options.name, user, token)
    elif arguments[0] == "publish":
        user, token = resolve_credentials(options.user, options.token, options.cred)
        if not check_path_exists(options.folder) and not check_path_exists(options.zip):
            show_error_and_exit("Please specify the folder of the spark package or the path " + \
                                "to the zip file.", p)
        if options.version is None or len(options.version.strip()) == 0:
            show_error_and_exit("Please specify a version for the release", p)
        publish_release(options.name, user, token, options.folder,
                        options.version, options.out, options.zip)
    else:
        show_error_and_exit("Unrecognized argument %s" % arguments[0])


if __name__ == '__main__':
    main()
