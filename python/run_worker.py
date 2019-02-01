import platform
import subprocess

if __name__ == '__main__':

    subprocess.run(['python', '-m', 'pip', 'install', '.'])
    subprocess.run(['python', 'setup.py', 'build'])
    subprocess.run(['python', '-m', 'azure.functions_worker'])