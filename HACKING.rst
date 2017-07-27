Style Commandments
==================

Read the OpenStack Style Commandments https://docs.openstack.org/hacking/latest/

Mistral Specific Commandments
-----------------------------

- [M001] Use LOG.warning(). LOG.warn() is deprecated.
- [M319] Enforce use of assertTrue/assertFalse
- [M320] Enforce use of assertIs/assertIsNot
- [M327] Do not use xrange(). xrange() is not compatible with Python 3. Use
  range() or six.moves.range() instead.
- [M328] Python 3: do not use dict.iteritems.
- [M329] Python 3: do not use dict.iterkeys.
- [M330] Python 3: do not use dict.itervalues.
