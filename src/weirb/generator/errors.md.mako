---
title: "Errors"
layout: page
date: ${date}
---

[TOC]

# Errors #

All service related errors are list here.

${'##'} Built-in Errors ${'##'}


Error Code        | Description
----------------- | -------------
%for error in builtin_errors:
${error['code']}  | ${error['doc'] or 'No Doc'}
%endfor

${'##'} Service Errors ${'##'}

% if service_errors:
Error Code        | Description
----------------- | -------------
    %for error in service_errors:
${error['code']}  | ${error['doc'] or 'No Doc'}
    %endfor
% else:
No Service Errors
% endif
