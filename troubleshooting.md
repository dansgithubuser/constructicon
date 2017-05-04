iOS keychain
------------

When automating a test on iOS, there's an extra dimension to reproducing a command: the keychain. The keychain is involved in signing your test so it can get onto the actual iOS device. If you get an error like:

```
Testing failed:
    No signing certificate "iOS Development" found:  No "iOS Development" signing certificate matching team ID "BLA5BLA555" with a private key was found.
    Code signing is required for product type 'Application' in SDK 'iOS 10.2'
```

Then it might be the case that your keychain is for some reason unavailable to your buildslave, despite using the same user and environment. To check, you can run

`security find-identity -p codesigning -v`

both from within the buildslave and as a human. If the output is different, something's up. Copying your iPhone Developer certificate to the System keychain using the Keychain Access utility application may solve this.
