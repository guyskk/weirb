---
title: "${name} Service"
layout: page
date: ${date}
---

[TOC]

# ${name} Service #

${doc or 'No Doc'}

%for method in methods:

${'##'} **${method['name']}** ${'##'}

${method['doc'] or 'No Doc'}

Params:
```
    %if method['is_http_request']:
HttpRequest
    %elif method['params'] is None:
No Params
    %else:
${method['params']}
    %endif
```

Returns:
```
    %if method['is_http_response']:
HttpResponse
    %elif method['params'] is None:
No Returns
    %else:
${method['returns']}
    %endif
```

    %if not method['raises']:
No Raises
    %else:
Raises:
        %for error in method['raises']:
            %if error['doc']:
    - ${error['code']}: ${error['doc']}
            %else:
    - ${error['code']}}
            %endif
        %endfor
    %endif
%endfor