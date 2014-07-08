
# echo bootstrapping packman...

# update and install prereqs
sudo apt-get -y update &&
sudo apt-get install -y curl python-dev rubygems rpm libyaml-dev &&

# install ruby
wget ftp://ftp.ruby-lang.org/pub/ruby/1.9/ruby-1.9.3-p547.tar.bz2
tar -xjf ruby-1.9.3-p547.tar.bz2
cd ruby-1.9.3-p547
./configure --disable-install-doc
make
sudo make install
cd ~

# install fpm and configure gem/bundler
sudo gem install fpm --no-ri --no-rdoc &&
echo -e 'gem: --no-ri --no-rdoc\ninstall: --no-rdoc --no-ri\nupdate:  --no-rdoc --no-ri' >> ~/.gemrc
echo -e 'gem: --no-ri --no-rdoc\ninstall: --no-rdoc --no-ri\nupdate:  --no-rdoc --no-ri' >> /root/.gemrc

# install pip
curl --silent --show-error --retry 5 https://bootstrap.pypa.io/get-pip.py | sudo python

# install packman
sudo pip install https://github.com/cloudify-cosmo/packman/archive/develop.tar.gz

# download backup components file (WORKAROUND UNTIL PACKMAN BUG IS FIXED)
cd ~
sudo wget https://dl.dropboxusercontent.com/u/407576/static_components.tar.gz &&
sudo tar -xzvf static_components.tar.gz -C / &&

# create cloudify components package
cd /cloudify-packager/ &&
sudo pkm make -c elasticsearch,logstash
sudo pkm pack -c cloudify-components

echo bootstrap done
echo NOTE: currently, using some of the packman's features requires that it's run as sudo.