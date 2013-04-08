%define pyver 27
%define pybasever 2.7

%define __python /usr/bin/python%{pybasever}
%define __os_install_post %{__python27_os_install_post}

%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Name:           python%{pyver}-palm
Version:        0.1.5post1
Release:        TEMPLATE
Summary:        Fast python protobufs library

Group:          Applications/System
License:        BSD
Source:         python%{pyver}-palm-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildRequires:  python%{pyver}
BuildRequires:  python%{pyver}-devel
BuildRequires:  python%{pyver}-distribute
BuildRequires:  python%{pyver}-simpleparse

Requires:       python%{pyver}-simpleparse

%define debug_package %{nil}


%description
This is a lightweight, fast library for using Google's protobufs in Python.

%prep
%setup -q -n python%{pyver}-palm-%{version}
find -name '*.py' | xargs sed -i '1s|^#!python|#!%{__python}|'


%build
CFLAGS="%{optflags}" %{__python} setup.py build


%check
%{__python} setup.py test


%install
rm -rf %{buildroot}
%{__python} setup.py install -O1 --skip-build \
    --root %{buildroot} \
    --single-version-externally-managed

rm -rf %{buildroot}%{python_sitelib}/setuptools/tests

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%doc LICENSE README.md
%{python_sitelib}/*
%{_bindir}/palmc
