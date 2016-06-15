constructicon
=============
Constructicon is a continuous integration system built upon buildbot. It seeks the same division of labor as hosted CI systems. In particular, maintainers of the system do just that, and users who want to take advantage of constructicon keep control of their build descriptions.

architecture
------------
The megatron controls the constructicons. The megatron is a buildbot master-slave pair. It is run by the maintainers. Users can request a build from the master, specifying a repo by URL, and the slave will create a constructicon for that repo.

The constructicons combine into the devastator. In particular, constructicons contribute builders to the devastator. The devastator also has a master and slaves. The devastator master is run by the megatron slave. Devastator slaves are run by the maintainers.

Maintainers describe the system to the megatron and devastator via cybertron.py, a Python script that goes in the root of this repo. It contains one dictionary, specifying things like network ports and slave descriptions.

Users describe their constructicon via constructicon.py, a Python script that goes in the root of their repo. It contains one dictionary, specifying things like desired platforms and what command to use to build.
