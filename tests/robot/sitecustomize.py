# Copyright 2025 - NetCracker Technology Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import ssl

# Python 3.13+ and urllib3 set ssl.VERIFY_X509_STRICT by default, enforcing
# RFC 5280 Key Usage on CA certificates. Legacy CAs without this extension
# cause "CA cert does not include key usage extension" errors.
# Zeroing the constant makes all `verify_flags |= VERIFY_X509_STRICT` a no-op.
if hasattr(ssl, 'VERIFY_X509_STRICT'):
    ssl.VERIFY_X509_STRICT = 0
