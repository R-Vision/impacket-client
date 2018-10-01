ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"/
if ! [ -x "$(command -v pip)" ]; then
  cd $ROOT_DIR/pip
  sudo python2.7 setup.py install
fi
cd $ROOT_DIR/six
sudo python2.7 setup.py install
cd $ROOT_DIR
sudo python2.7 -m pip install pycryptodomex-3.6.6-cp27-cp27mu-manylinux1_x86_64.whl
cd $ROOT_DIR