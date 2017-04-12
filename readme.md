constructicon
=============
Constructicon is a continuous integration system built upon buildbot. It seeks the same division of labor as hosted CI systems. In particular, maintainers of the system do just that, and users who want to take advantage of constructicon keep control of their build descriptions.

architecture
------------
The megatron controls the constructicons. The megatron is a buildbot master-slave pair. It is run by maintainers. Users can request a build from the master, specifying a repo by URL, and the slave will create a constructicon for that repo.

The constructicons combine into the devastator. The devastator has a buildbot master and slaves. The devastator master is run by the megatron slave. A devastator slave can be run by maintainers or a user. Devastator builders are defined by constructicons.

Maintainers describe the system to the megatron and devastator via cybertron.py. It contains one dictionary, specifying things about the system.

Users describe their constructicon via constructicon.py, which goes in the root of their repo. It should set a dictionary called constructicon, specifying how their repo should be built.

devastator directory structure
------------------------------
- devastator/constructicons - Clones of repos created by megatron for the purpose of reading a constructicon.py config file.
- devastator/master/<builder> - Build results.
- devastator/slave/<slave>/constructicons/<repo> - Deps folder.
- devastator/slave/<slave>/constructicons/<repo>/<repo> - Build folder.

known issues
------------
Megatrons must be run on non-Windows machines. On Windows, `buildbot stop` does not work, which means a megatron cannot restart its devastator, which defeats the entire purpose of the effort. I think the problem is with Python 2's Popen's kill. Python 3's Popen's kill does work. Therefore I'm not going to make a workaround for this, preferring to wait for Python 3 support from buildbot.
