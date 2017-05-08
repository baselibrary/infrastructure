# Store Secrets using Hashicorp Vault

# Learn how to store and manage secrets using Hashicorp Vault

# Step 1 - Configuration

cat vault.hcl
backend "consul" {
  address = "consul:8500"
  advertise_addr = "consul:8300"
  scheme = "http"
}
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = 1
}
disable_mlock = true

# Create Data Container
# To store the configuration we'll create a container. This will be used by Vault and Consul to read the required configuration files.

docker create -v /config --name config busybox; docker cp vault.hcl config:/config/;

# Step 2 - Launch
# With the configuration data container created we can launch the required processes to start Vault.
# Launch Services

docker run -d --name consul \
     -p 8500:8500 \
    consul:v0.6.4 \
    agent -dev -client=0.0.0.0

# Our Vault instance can now use Consul to store the data. All data stored within Consul will be encrypted.

docker run -d --name vault-dev \
  --link consul:consul \
  -p 8200:8200 \
  --volumes-from config \
  cgswong/vault:latest server -config=/config/vault.hcl

# Step 3 - Initialise
# With a vault instance running we can now configure our environment and initialise the Vault.
# Configure Environment

alias vault='docker exec -it vault-dev vault "$@"'
export VAULT_ADDR=http://127.0.0.1:8200

# Initialise Vault
# With the alias in place, we can make calls to the CLI. The first step is to initialise the vault using the init command.

vault init -address=${VAULT_ADDR} > keys.txt
cat keys.txt

# Step 4 - Unseal Vault

vault unseal -address=${VAULT_ADDR} $(grep 'Key 1:' keys.txt | awk '{print $NF}')
vault unseal -address=${VAULT_ADDR} $(grep 'Key 2:' keys.txt | awk '{print $NF}')
vault unseal -address=${VAULT_ADDR} $(grep 'Key 3:' keys.txt | awk '{print $NF}')
vault status -address=${VAULT_ADDR}

# Step 5 - Vault Tokens
# You can use this token to login to vault.

export VAULT_TOKEN=$(grep 'Initial Root Token:' keys.txt | awk '{print substr($NF, 1, length($NF)-1)}')
vault auth -address=${VAULT_ADDR} ${VAULT_TOKEN}

# Step 6 - Read/Write Data
# Save Data
# To store data, we use the write CLI command. In this case, we have a key named secret/api-key with the value 12345678

vault write -address=${VAULT_ADDR} \
  secret/api-key value=12345678

# Read Data
# Reading the key will output the value, along with other information such as the lease duration.
vault read -address=${VAULT_ADDR} \
  secret/api-key

# You can also use the -field flag to extract the value from the secret data.

vault read -address=${VAULT_ADDR} \
  -field=value secret/api-key

# Step 7 - HTTP API
# Using the command like tool jq we can parse the data and extract the value for our key.

curl -H "X-Vault-Token:$VAULT_TOKEN" \
  -XGET http://docker:8200/v1/secret/api-key

curl -s -H  "X-Vault-Token:$VAULT_TOKEN" \
  -XGET http://docker:8200/v1/secret/api-key \
  | jq -r .data.value

# Step 8 - Consul Data
# As Vault stores all the data as encrypted key/values in Consul you can use the Consul UI to see the encrypted data.
