---
title: "${name} Service"
layout: page
date: ${date}
---

[TOC]

# ${name} Service #

${doc or 'No Doc'}

%for handler in handlers:

${'##'} \
%if handler['is_method']:
Method: \
%else:
View: \
%endif
**${handler['name']}** ${'##'}

${handler['doc'] or 'No Doc'}

**Routes**:

Path         | Methods
------------ | ----------------
%for route in handler['routes']:
${route['path']} | ${route['methods']}
%endfor

%if handler['is_method']:
**Params**:
```
    %if handler['params'] is None:
No Params
    %else:
${handler['params']}
    %endif
```
%endif

**Returns**:
```
    %if handler['returns'] is None:
No Returns
    %else:
${handler['returns']}
    %endif
```

    %if not handler['raises']:
**No Raises**
    %else:
**Raises**:

Status Code  | Error Code        | Description
------------ | ----------------- | -------------
%for error in handler['raises']:
${error['status']}  | ${error['code']}  | ${error['doc'] or 'No Doc'}
%endfor
    %endif
%endfor
