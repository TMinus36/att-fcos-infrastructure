imph@fedora-server ~/P/h/d/production-final [127]> VAULT_ADDR=http://10.0.0.109:8200 vault operator init -key-shares

Unseal Key 1: 3Iq/s4LRi02B+I9K9Um+CHLF34cECyVSAeI6PqRRJ+4=

Initial Root Token: hvs.tu4C6bxdDR3y2b7GkVsj8ZFk

Vault initialized with 1 key shares and a key threshold of 1. Please securely
distribute the key shares printed above. When the Vault is re-sealed,
restarted, or stopped, you must supply at least 1 of these keys to unseal it
before it can start servicing requests.

Vault does not store the generated root key. Without at least 1 keys to
reconstruct the root key, Vault will remain permanently sealed!

It is possible to generate new unseal keys, provided you have a quorum of
existing unseal keys shares. See "vault operator rekey" for more information.
timph@fedora-server ~
