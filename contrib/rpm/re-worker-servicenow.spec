%if 0%{?rhel} && 0%{?rhel} <= 6
%{!?__python2: %global __python2 /usr/bin/python2}
%{!?python2_sitelib: %global python2_sitelib %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")}
%{!?python2_sitearch: %global python2_sitearch %(%{__python2} -c "from distutils.sysconfig import get_python_lib; print(get_python_lib(1))")}
%endif

%global _pkg_name replugin
%global _src_name reworkerservicenow

Name: re-worker-servicenow
Summary: ServiceNow worker for Release Engine
Version: 0.0.4
Release: 1%{?dist}

Group: Applications/System
License: AGPLv3
Source0: %{_src_name}-%{version}.tar.gz
Url: https://github.com/rhinception/re-worker-servicenow

BuildArch: noarch
BuildRequires: python2-devel, python-setuptools
Requires: re-worker, python-requests

%description
A ServiceNow worker for Rease Engine provides basic change record
access.

%prep
%setup -q -n %{_src_name}-%{version}

%build
%{__python2} setup.py build

%install
%{__python2} setup.py install -O1 --root=$RPM_BUILD_ROOT --record=re-worker-servicenow-files.txt

%files -f re-worker-servicenow-files.txt
%defattr(-, root, root)
%doc README.md LICENSE AUTHORS
%dir %{python2_sitelib}/%{_pkg_name}
%exclude %{python2_sitelib}/%{_pkg_name}/__init__.py*


%changelog
* Thu Jan  8 2015 Steve Milner <stevem@gnulinux.net> - 0.0.4-1
- Now can query and create CTasks.

* Thu Dec  4 2014 Tim Bielawa <tbielawa@redhat.com> - 0.0.3-4
- Emit 'start' messages once running

* Wed Nov 19 2014 Tim Bielawa <tbielawa@redhat.com> - 0.0.3-3
- Fix logic in start/end time update method

* Mon Nov 17 2014 Tim Bielawa <tbielawa@redhat.com> - 0.0.3-2
- Return 'exists' as True if auto-creation succeeds

* Mon Nov 17 2014 Tim Bielawa <tbielawa@redhat.com> - 0.0.3-1
- Now with automatic change record creation, if you're into that sort of thing

* Wed Sep 24 2014 Steve Milner <stevem@gnulinux.net> - 0.0.2-1
- Now can update custom environment start/end dates.

* Thu Jul 17 2014 Steve Milner <stevem@gnulinux.net> - 0.0.1-1
- Initial spec
