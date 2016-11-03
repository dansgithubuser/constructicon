#used in go.py example and tests
{
	'help-linux': {
		'features': {'platform': 'linux'},
		'commands': ['python go.py -h'],
		'upload': {'readme.md': 'readme-dest.md'},
	},
	'sleep': {
		'commands': ['python -c "import time; time.sleep(10)"'],
	},
	'deps': {
		'deps': ['https://github.com/dansgithubuser/playground'],
		'commands': ['python ../playground/timestamp.py'],
	},
}
