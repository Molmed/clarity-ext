# clarity-ext
NOTE: Work in progress (pre-alpha).

Provides a library for extending Clarity LIMS in a more developer-friendly way.

## Problem 
Any LIMS system needs to be scripted (extended), as any lab has its own workflows. One extension could
be to create a driver file for a robot when the user presses a button in a workflow step.

The Clarity LIMS server provides extensibility in the form of so called EPPs. These are basically
shell commands that can be run on certain events in the system.

To develop and validate these steps, the developer would need to change the configuration entry for the
script in the LIMS and then run the script manually through the LIMS.

This method is cumbersome and doesn't provide an acceptable feedback loop for the developer.

## Solution
With `clarity-ext`, the developer can instead:
  * Set a step up as usual
  * Write an extension that should run in this step
  * Run (integration test) the extension from his development environment
  * All requests/responses are cached, so the integration test will run fast. Furthermore, the test
    can still be executed after the step has been deleted or altered. 
  * Extensions have access to extension contexts, which do most of the work. This way, the readability 
    and simplicity of the extensions increase, allowing non-developers to review and alter the code.

## Components
### Runner
The first component of the system is the `clarity-ext` command line tool. All extensions are run through this tool.

For example, we have an extension that generates an input file for a Fragment Analyzer.
The `Process Type`s  EPP is set up like this in that case:
```
clarity-ext extension --args 'pid={processLuid}' clarity_ext_scripts.fragment_analyzer.create_fa_input_file exec
```

However, when developing, developer runs this instead:
```
clarity-ext extension clarity_ext_scripts.fragment_analyzer.create_fa_input_file test
```

These are the differences between the commands:
  * The latter one uses a cache for requests/responses
  * The first one needs to provide the pid as an argument, while the second uses the test data defined in the extension

The end result is that the user will get feedback directly in the IDE or terminal when running. It's faster because of
caching, but the tool will also output the file to stdout.

### Extensions
The clarity_ext_scripts module includes extensions that have been implemented for the SNP&SEQ technology platform at
Uppsala University. Some might be directly applied in another lab, but they are generally there as samples only.

The developer creates an extension by subclassing one of the extension base classes and implementing or overriding
one or more method.

Currently, there are two extension base classes:
  * `GeneralExtension`: The extensions's `execute` method will be run on execution
  * `DriverFileExtension`: Provides methods that describe the file

All extensions have access to the `ExtensionContext`. This object provides a higher level view on the data available
from the Clarity REST API. The extension can also import generic helper classes. All of the properties on this
object are generated lazily (on request), and an exception is thrown if they can't be used in the particular context
for some reason.

All extensions in the clarity_ext_scripts folder follow the design principle of leaving all non-trivial or boilerplate
code to the framework. The idea is that they can be understood by non-developers configuring or validating the system.
Furthermore, the idea is that all new extensions are made only with this framework.

### Helper modules
* clarity_ext.domain: Provides classes that help with work directly related to labs, such as a Plate object that
  can enumerate wells in different ways.
* clarity_ext.pdf: Provides ways to work with pdf files in a high level way, such as splitting them
