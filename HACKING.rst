Style Commandments
==================

Read the OpenStack Style Commandments http://docs.openstack.org/developer/hacking/

Mistral Specific Commandments
-----------------------------

- [M318] Change assertEqual(A, None) or assertEqual(None, A) by optimal assert
  like assertIsNone(A)
- [M327] Do not use xrange(). xrange() is not compatible with Python 3. Use
  range() or six.moves.range() instead.
