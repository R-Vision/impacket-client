ROOT_DIR=`pwd`
cd $ROOT_DIR/six
sudo python2.7 setup.py install
cd $ROOT_DIR
sudo python2.7 -m pip install pycryptodomex-3.6.6-cp27-cp27mu-manylinux1_x86_64.whl
cd $ROOT_DIR