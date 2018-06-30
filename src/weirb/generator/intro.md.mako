---
title: "Introduction"
layout: page
date: ${date}
---

[TOC]

${intro}

${'##'} Services ${'##'}

%for service in services:
- [${service['name']}](/services/${service['name']}.html)
%endfor

${'##'} Built-in HRPC Errors ${'##'}

Status Code  | Error Code        | Description
------------ | ----------------- | -------------
%for error in builtin_errors:
${error['status']}  | ${error['code']}  | ${error['doc'] or 'No Doc'}
%endfor
