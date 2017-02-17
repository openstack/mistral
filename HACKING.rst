Style Commandments
==================

Read the OpenStack Style Commandments http://docs.openstack.org/developer/hacking/

Mistral Specific Commandments
-----------------------------

- [M318] Change assertEqual(A, None) or assertEqual(None, A) by optimal assert
  like assertIsNone(A)
- [M327] Do not use xrange(). xrange() is not compatible with Python 3. Use
  range() or six.moves.range() instead.
- [M328] Python 3: do not use dict.iteritems.
- [M329] Python 3: do not use dict.iterkeys.
- [M330] Python 3: do not use dict.itervalues.
