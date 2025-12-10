os keypair create drai-inn-keypair > drain-inn-keypair.key
chmod 600 drai-inn-keypair.key 
export GCLOUD_PROJECT=mygen3
gsecret save digital-twins-drai-inn-keypair file:drai-inn-keypair.key 
