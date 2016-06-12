password='uuvdj_ksdjcls2dnwzxo'

def repo_url_to_name(repo_url):
	name=repo_url.split('/')[-1]
	if name.endswith('.git'): name=name[:-4]
	return name
