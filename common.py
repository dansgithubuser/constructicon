import subprocess

password='uuvdj_ksdjcls2dnwzxo'

def repo_url_to_name(repo_url):
	name=repo_url.split('/')[-1]
	if name.endswith('.git'): name=name[:-4]
	return name

def git_state():
	result=subprocess.check_output('git rev-parse HEAD', shell=True).strip()
	if(
		subprocess.check_output('git diff'         , shell=True).strip()
		or
		subprocess.check_output('git diff --cached', shell=True).strip()
	): result+=' with diff'
	return result
