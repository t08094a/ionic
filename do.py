#!/usr/bin/env python3

""" Actions to execute for this project """

""" 
Requirements: 
    pip3 install inquirer
    pip3 install colorama
"""

import inquirer
import subprocess
import colorama
from colorama import Fore, init
import os
import shutil
import configparser
import signal
from collections import OrderedDict

init(autoreset=True)

settings_file_name = '.local_settings.ini'

build_docker_image = 'Build Docker Image'
create_app = 'Erzeuge App Template'
ionic_serve = 'Debug mit ionic serve'
internal_runner_script = 'Starte Runner Script in Docker'
start_bash = 'Starte Bash in Docker'
cancel = 'Abbruch'

def write_content_to_local_settings(section: str, key: str, value: str):
    """
    Writes a key value pair to a specific section in the local settings file

    :param section: The section to write the key value pair into
    :param key: The key of the key value pair
    :param value: The value of the key value pair
    """

    config = configparser.ConfigParser()
    config.read(settings_file_name)

    if(not config.has_section(section)):
        config.add_section(section)
    
    config[section][key] = value
    
    with open(settings_file_name, 'w') as configfile:
        config.write(configfile)


def read_content_from_local_settings(section: str, key: str, fallback=configparser._UNSET):
    config = configparser.ConfigParser()
    config.read(settings_file_name)

    value = config.get(section, key, fallback=fallback)
    return value


def get_docker_images_based_on_settings():
    image_name = read_content_from_local_settings('Docker', 'image_name')
    
    docker_image_args = ['docker', 'images', '--format', '\"table {{.Repository}}||{{.Tag}}\"']

    if(image_name):
        docker_image_args.extend(['--filter=reference=\'' + image_name + '\''])
    
    completed = subprocess.run(' '.join(docker_image_args), shell=True, stdout=subprocess.PIPE, universal_newlines=True, check=True)
    lines = str(completed.stdout).splitlines()[1::]
    items = [n.split('||') for n in lines]
    items = [':'.join(n) for n in items]

    return items


def move_all_files(srcDir: str, destDir: str):
    sourceFiles = [os.path.join(srcDir, file) for file in os.listdir(srcDir)]
    
    for filePath in sourceFiles:
        shutil.move(filePath, destDir)

def action_build_docker_image():
    print(build_docker_image)

    # DOCKER_BUILDKIT=1
    #os.environ['DOCKER_BUILDKIT'] = "1" # visible in this process + all children

    questions = [
        inquirer.Text('name', message='Welchen Namen soll der Build erhalten?', default='t08094a/ionic'),
        inquirer.Text('version', message='Welche Version soll der Build erhalten?', default='1.0.0'),
        inquirer.Confirm('latest', message='Soll mit \'latest\' geflagt werden?', default=True),
        inquirer.Confirm('with_cache', message='Soll mit Dockers Cache gebaut werden?', default=True)
    ]

    answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
    
    name = answers['name']
    version = answers['version']
    latest = answers['latest']
    with_cache = answers['with_cache']

    # save the image name in an invisible file
    write_content_to_local_settings('Docker', 'image_name', name)

    cmd = [
        'docker', 'build',
        '--build-arg', 'USER_ID=$(id -u ${USER})',
        '--build-arg', 'GROUP_ID=$(id -g ${USER})',
        '-t', name + ':' + version
    ]

    if(latest):
        cmd.extend(['-t', name + ':latest'])

    if(not with_cache):
        cmd.extend(['--no-cache'])

    cmd.extend(['.'])
    
    # z.B. docker build -t t08094a/ionic:1.0.0 -t t08094a/ionic:latest .
    print(Fore.CYAN + 'call: ' + ' '.join(cmd) + '\n')
    completed = subprocess.run(cmd)


def action_create_app():
    print(create_app)

    docker_image_names = get_docker_images_based_on_settings()
        
    questions = [inquirer.Text('app_name', message='Welchen Namen soll die App erhalten?', validate=True)]

    if(len(docker_image_names) > 1):
        questions.append(inquirer.List('image', message='Welches Image soll zur Ausführung verwendet werden?', choices=docker_image_names, default=docker_image_names[0]))

    answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
    app_name = answers['app_name']
    image = answers['image']

    write_content_to_local_settings('App', 'name', app_name)

    os.makedirs(app_name, exist_ok=True)
    local_volume = os.path.join(os.getcwd(), app_name)

    cmd = 'docker run --rm -v {}:/myApp -v /etc/passwd:/etc/passwd:ro -v /etc/group:/etc/group:ro -v /etc/shadow:/etc/shadow:ro -w /myApp -it -u {}:{} {} bash -c \'ionic start {} --no-git\''.format(local_volume, os.getuid(), os.getgid(), image, app_name)
    print(Fore.CYAN + 'call: ' + cmd)
    completed = subprocess.run(cmd, shell=True, check=True)

    # move all created files to the parent directory and remove the temp one
    tmp_src_path = os.path.join(local_volume, app_name)
    move_all_files(tmp_src_path, local_volume)
    os.rmdir(tmp_src_path)

def action_ionic_serve():
    print(ionic_serve)

    docker_image_names = get_docker_images_based_on_settings()
        
    questions = [inquirer.List('image', message='Welches Image soll zur Ausführung verwendet werden?', choices=docker_image_names, default=docker_image_names[0])]

    answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
    image = answers['image']

    app_name: str = read_content_from_local_settings('App', 'name')
    if(not app_name):
        print(Fore.RED + '\'name\' ist nicht in der Sektion \'App\' definiert')
        return

    port = read_content_from_local_settings('App', 'development_port', fallback=8100)
    working_dir = os.path.join(os.getcwd(), app_name)

    cmd = """
        docker run --rm --init \
        -e CHOKIDAR_USEPOLLING=\'1\' -e IONIC_PORT=\'{port}\' \
        -p 3000:3000 -p 5000:5000 -p {port}:8100 -p 8080:8080 -p 9876:9876 -p 35729:35729 \
        -v {}:/myApp -v /etc/passwd:/etc/passwd:ro -v /etc/group:/etc/group:ro -v /etc/shadow:/etc/shadow:ro \
        -w /myApp -it -u {}:{} {} \
        ionic serve --all -b --address 0.0.0.0 --port {port}""" \
        .format(working_dir, os.getuid(), os.getgid(), image, port=port).lstrip()

    print(Fore.CYAN + 'call: ' + cmd)
    try:
        p = subprocess.Popen(cmd.split()).communicate()
    except KeyboardInterrupt:
        print('SIGINT received')
        p.send_signal(signal.SIGINT)

def action_internal_runner_script():
    print(internal_runner_script)

    docker_image_names = get_docker_images_based_on_settings()
        
    questions = [inquirer.List('image', message='Welches Image soll zur Ausführung verwendet werden?', choices=docker_image_names, default=docker_image_names[0])]

    answers = inquirer.prompt(questions, raise_keyboard_interrupt=True)
    image = answers['image']

    app_name: str = read_content_from_local_settings('App', 'name')
    if(not app_name):
        print(Fore.RED + '\'name\' ist nicht in der Sektion \'App\' definiert')
        return

    port = read_content_from_local_settings('App', 'development_port', fallback=8100)
    working_dir = os.path.join(os.getcwd(), app_name)

    cmd = 'docker run --rm --init -e CHOKIDAR_USEPOLLING=\'1\' -p 3000:3000 -p 5000:5000 -p {port}:8100 -p 8080:8080 -p 9876:9876 -p 35729:35729 -v {}:/myApp -v /etc/passwd:/etc/passwd:ro -v /etc/group:/etc/group:ro -v /etc/shadow:/etc/shadow:ro -w /myApp -it -u {}:{} {} runner.py'.format(working_dir, os.getuid(), os.getgid(), image, port=port)
    print(Fore.CYAN + 'call: ' + cmd)
    try:
        p = subprocess.Popen(cmd.split()).communicate()
    except KeyboardInterrupt:
        print('SIGINT received')
        p.send_signal(signal.SIGINT)


def action_start_bash():
    print(start_bash)

    docker_image_names = get_docker_images_based_on_settings()

    image = ''

    if(len(docker_image_names) > 1):
        questions = [
            inquirer.List('image', message='Welches Image soll zur Ausführung verwendet werden?', choices=docker_image_names, default=docker_image_names[0])
        ]
        answer = inquirer.prompt(questions, raise_keyboard_interrupt=True)
        image = answer['image']
    else:
        image = docker_image_names[0]

    port = read_content_from_local_settings('App', 'development_port', fallback=8100)

    cmd = """
        docker run --rm \
        -e CHOKIDAR_USEPOLLING=\'1\' -e IONIC_PORT=\'{port}\' \
        -p 3000:3000 -p 5000:5000 -p {port}:8100 -p 8080:8080 -p 9876:9876 -p 35729:35729 \
        -v {}:/myApp -v /etc/passwd:/etc/passwd:ro -v /etc/group:/etc/group:ro -v /etc/shadow:/etc/shadow:ro \
        -w /myApp -it -u {}:{} {} bash """ \
        .format(os.getcwd(), os.getuid(), os.getgid(), image, port=port).lstrip()
    
    print(Fore.CYAN + 'call: ' + cmd)
    completed = subprocess.run(cmd, shell=True)


def action_cancel():
    # do nothing
    pass


if __name__ == '__main__':

    options = OrderedDict([
        (build_docker_image, action_build_docker_image),
        (create_app, action_create_app),
        (ionic_serve, action_ionic_serve),
        (internal_runner_script, action_internal_runner_script),
        (start_bash, action_start_bash),
        (cancel, action_cancel)
    ])

    questions = [
        inquirer.List('selection',
                      message="Welche Aktion soll ausgeführt werden?",
                      choices=list(options))
    ]

    try:
        answer = inquirer.prompt(questions, raise_keyboard_interrupt=True)
        target = answer['selection']

        options[target]()
    except KeyboardInterrupt:
        pass
