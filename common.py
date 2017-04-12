import os, subprocess

folder=os.path.split(os.path.realpath(__file__))[0]

password='uuvdj_ksdjcls2dnwzxo'

def repo_url_to_name(repo_url):
	name=repo_url.split('/')[-1]
	if name.endswith('.git'): name=name[:-4]
	return name

def git_state_has_diff():
	return (
		subprocess.check_output('git diff'         , shell=True).strip()
		or
		subprocess.check_output('git diff --cached', shell=True).strip()
	)

def git_state():
	result=subprocess.check_output('git rev-parse HEAD', shell=True).strip()
	if(git_state_has_diff()): result+=' with diff'
	return result

def sane_step(Step, **kwargs):
	if 'haltOnFailure' not in kwargs: kwargs['haltOnFailure']=True
	if 'warnOnWarnings' not in kwargs: kwargs['warnOnWarnings']=True
	return Step(**kwargs)

def constructicon_slave_go(options):
	return 'python {} {}'.format(os.path.join(*['..']*6+['go.py']), options)

def execute(file_name, var):
	with open(file_name) as file: contents=file.read()
	x={
		var: None,
		'constructicon_slave_go': constructicon_slave_go
	}
	try: exec(contents, x)
	except:
		print('exception raised while executing {}'.format(file_name))
		raise
	return x[var]

def constructicon(folder):
	return execute(os.path.join(folder, 'constructicon.py'), 'constructicon')

def cybertron_folder():
	with open(os.path.join(folder, 'cybertron.txt')) as file: return file.read()

def cybertron():
	return execute(os.path.join(cybertron_folder(), 'cybertron.py'), 'cybertron')

def cybertron_git_state():
	start=os.getcwd()
	os.chdir(cybertron_folder())
	result=git_state()
	os.chdir(start)
	return result
