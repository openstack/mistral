Mistral Coding Guidelines
=========================

Why learn more coding guidelines?
---------------------------------

This document contains the description of the guidelines used for writing
code on the Mistral project. Some of the guidelines follow from the
nature of Python programming language (dynamic types, etc), some are the
result of the consensus achieved by the project contributors during many
contribution cycles. All contributors need to follow these guidelines
when contributing to Mistral. The purpose of having such well described
practices is improving communication between team members, reducing a number
of controversial situations related to how a certain code snippet should
be written, and letting contributors focus on unique engineering tasks
rather than low level decisions that any engineer makes many times a day,
like choosing a good name for a class or variable, or how to organise a loop,
whether they need to put a blank line before "if" or "return", in what cases
and so on. The document, when accepted and followed by team members, aims
to improve overall development speed and quality.

Note that the guidelines described below almost don't conflict with the
official PEP8 style guide (https://www.python.org/dev/peps/pep-0008/)
describing how any Python program should be formatted. Mistral guidelines
add more high level semantics on top of it. PEP8 still should be considered
a necessary base for those who write Python programs. Strictly speaking,
this guide is not exactly about style, it's about writing maintainable code.

Some of the concepts being discussed below may seem a bit too philosophical
but, in fact, they reflect our real experience of solving practical tasks.
According to it, some decisions work well and some don't given the Python
programming nature and the nature of the project.

The guidelines are based on the three main values:

- **Communication.** When writing code we always try to create it in a way
  that it's easy to read and understand. This is important because most of
  the time developers spend on reading existing code, not writing new.
- **Simplicity.** It makes sense to write code that uses minimal means that
  solves a task at hand.
- **Flexibility.** In most cases it's better to keep options open because
  in programming there's no such thing as "done". Pretty much all code gets
  modified during lifecycle of a program working in production. This is a
  very important difference form designing real buildings where we can't
  rebuild a basement after a building is completed and inhabited by people.

In the document, there is a number of code snippets, some are considered
incorrect and some are correct, with explanations why from the perspective
of these key values.

Further sections are devoted to certain aspects of writing readable code.
They will typically have a list of guidelines upfront so it's easy to find
them in the text and then more details on them, if needed.

Naming
------

Naming is always important in programing. Good naming should always serve
for better communication, i.e. a name of a code entity (module, variable,
class etc.) should convey a clear message to a code reader about the meaning
of the entity. For dynamic languages naming is even more important than for
languages with static types. Below it will be shown why.

Using Abbreviations
^^^^^^^^^^^^^^^^^^^

Guidelines
''''''''''

 - *Use well-known abbreviations to name variables, method arguments, constants*

Well-known abbreviations (shortcuts) used for names of constants, local
variables and method arguments help simplify code, since it becomes less
verbose, and simultaneously improve communication because all team members
understand them the same way. Below is a list of abbreviations used on the
Mistral project. The list is not final and is supposed to grow over time.

 - **app** - application
 - **arg** - argument
 - **cfg** - configuration
 - **cls** - class
 - **cmd** - command
 - **cnt** - count
 - **ctx** - context
 - **db** - database
 - **desc** - description
 - **dest** - destination
 - **def** - definition
 - **defs** - definitions
 - **env** - environment
 - **ex** - execution
 - **execs** - executions
 - **exc** - exception
 - **log** - logger
 - **ns** - namespace
 - **info** - information
 - **obj** - object
 - **prog** - program
 - **spec** - specification
 - **sync** - synchronous
 - **wf** - workflow
 - **wfs** - workflows

Note that when using a well-known abbreviation to name a constant we need to
use capital letters only (just as required by PEP8).

Local Variables and Method Arguments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Guidelines
''''''''''

 - *The name of a method argument should clearly communicate its semantics
   and purpose*
 - *The name of a method argument or a local variable should include a type
   name if it creates an ambiguity otherwise*
 - *The name of a local variable can be shortened from a full word (up to one
   letter) if the scope of the variable is very narrow (several lines) and if
   it doesn't create ambiguities*

Principles of choosing names in dynamic languages like Python are especially
important because oftentimes we don't clearly see of what type a certain
variable is. Whereas a type itself (no matter if it's primitive or represented
by a class) carries very important information about all objects of this type.
For example, if we see a variable in Java or C++ code it's not a problem to
find out of what type this variable is, we can easily find where the variable
is defined. Any modern IDE also allows to navigate to a type declaration (e.g.
if it's a class) just by clicking on it and see all required info about it.
In Python, it's often much more problematic to find a variable type. Injecting
a type name, at least a shortcut, into a variable name often helps mitigate
this fundamental issue and improve code readability, and hence communication.

Below are the code snippets that help illustrate this problem. Let's assume we
have the following Python classes:

 .. code-block:: python

    class TaskExecution(Execution):
        # Carries information about a running task.
        ...

    class TaskSpec(BaseSpec):
        # Defines a work logic of a particular task.
        ...

For what we want to illustrate, it's not important if they belong to the same
module or different.

Problematic Code
''''''''''''''''

 .. code-block:: python

    def calculate_next_tasks(self, task, context):
        result = set()

        for clause in task.get_on_clauses():
            task_names = self.evaluate_on_clause(clause, context)

            tasks = [self.get_task_by_name(t_n) for t_n in task_names]

            result.update(tasks)

        return result

Is this method easy to understand? Well, if this code is part of a small
program (e.g. a 200-300 lines script) then it may be ok. But when it's a
system with dozens of thousands lines of code then it has a number of issues.

The most important issue is that we don't know the type of the "task" method
argument. In order to find it we'll have to see where this method is called
and what is passed as an argument. Then, if an object is not created there
we'll have to go further and find callers of that method too, and so on until
we find where the object is actually instantiated. The longer the method call
chains are, the worse. So, jus by looking at this code we can't determine
whether the argument "task" is of type TaskSpec or TaskExecution. So for
example, we can't even say for sure if ``task.get_on_clauses()`` is a correct
instruction. If we have hundreds of places like this, it is very challenging
to read code and it is very easy to make a mistake when modifying it.

The other obvious issues are also related to naming:

#. It's not clear objects of what type are returned by the method
#. It's not clear objects of what type is returned by
   ``self.get_task_by_name(t_n)``

Better Code
'''''''''''

 .. code-block:: python

    def calculate_next_task_specs(self, task_spec, context):
        result = set()

        for clause in task_spec.get_on_clauses():
            task_names = self.evaluate_on_clause(clause, context)

            task_specs = [self.get_task_spec_by_name(t_n) for t_n in task_names]

            result.update(task_specs)

        return result

Now we won't be confused. Of course, we still have to remember we have those
two classes but at least we have a clear pointer to a type.

Functions and Methods
^^^^^^^^^^^^^^^^^^^^^

Guidelines
''''''''''

 - *The name of a method should clearly communicate its semantics and purpose*
 - *The name of a method should include a type name of a returned value when it
   creates an ambiguity otherwise*


For example, there are two classes like these again:

 .. code-block:: python

    class TaskExecution(Execution):
        # Carries information about a running task.
        ...

    class TaskSpec(BaseSpec):
        # Defines a work logic of a particular task.
        ...

And we need a method that implements some logic and returns an instance of
**TaskSpec**. How would we choose a good name for the method?

Problematic Code
''''''''''''''''

.. code-block:: python

    def calculate_parent_task(self, task_spec):
        ...

Looking at this method signature it's not clear what to expect as a returned
value since in Python method declarations don't contain a returned type value.
Although there's a temptation to use just "task" in the method name it leads
to the naming ambiguity: a returned value may be either of **TaskExecution**
or **TaskSpec** type. Strictly speaking, it may be any type since it's Python
but we can help a reader of this code a little bit and leave a hint about
what's going to be returned from the method when it's called.

At first glance, it may seem a bit weird why we pay attention to such things.
One may say that it's already totally clear that need to use full "task_spec"
in the method name instead of "task" just according to the name of the class.
Why anybody may want to use "task"? So, the reality is that during informal
communication within a team people tend to simplify/shorten words. That is,
when several team members are working on something related to task
specifications within a certain scope (module, class, etc.) they often move
to using a simplified terminology and instead of saying "task specification"
they start saying just "task". And this kind of habit often also sneaks into
code. And eventually it breaks communication between code author and code
reader.

Better Code
'''''''''''

.. code-block:: python

    def calculate_parent_task_spec(self, task_spec):
        ...

Although it's more verbose, it allows to mitigate the naming ambiguity for
a code reader.

Constants
^^^^^^^^^

Guidelines
''''''''''

 - *All hardcoded values (strings, numbers, etc.) must be defined as
   constants, i.e. global module variables*
 - *Constants must be defined in the beginning of a module*

Problematic Code
''''''''''''''''

.. code-block:: python

    def print_task_report_line(self, line, level=0):
        self.app.stdout.write(
            "task: %s%s\n" % (' ' * (level * 4), line)
        )

    ...

    def print_action_report_line(self, line, level=0):
        self.app.stdout.write(
            "action: %s%s\n" % (' ' * (level * 4), line)
        )

The problem of this code is that it uses hard-coded integer values at
different places. Why is it a problem?

 - It's hard to find hard-coded values while reading code
 - It's hard to understand whether same values mean semantically the same
   thing, or different
 - It's easy to make a mistake when changing a hard-coded value because we
   can change it at one place and miss other places

Better Code
'''''''''''

.. code-block:: python

    REPORT_ENTRY_INDENT = 4
    DEFAULT_ENTRY_LEVEL = 0

    def print_task_report_line(self, line, level=DEFAULT_ENTRY_LEVEL):
        self.app.stdout.write(
            "task: %s%s\n" % (' ' * (level * REPORT_ENTRY_INDENT), line)
        )

    ...

    def print_action_report_line(self, line, level=DEFAULT_ENTRY_LEVEL):
        self.app.stdout.write(
            "action: %s%s\n" % (' ' * (level * REPORT_ENTRY_INDENT), line)
        )

Now the code clearly communicates to a reader that value 4 in these two
methods means exactly the same entity: an indent of any report entry. The
other constant similarly adds clarity about value 0. Previously, these two
integers were nameless. It's now also easy to change values, we just need
to set different values to the named constants.

Grouping and Blank Lines
------------------------

Guidelines
^^^^^^^^^^
 - *Use blank lines to split individual steps (units) of algorithms.*
 - *Always put blank lines before and after "if", "for", "try" and "with"
   blocks if they don't contain one another w/o anything else in between.*
 - *Always put a blank line before "return" unless it's the only instruction
   in en enclosing code block like a method or an "if" block.*
 - *Use blank lines to split logically not symmetric lines, e.g. less
   abstract and more abstract lines like variable assignment and a method
   call.*
 - *Put a blank line after any call to a superclass.*

Although for someone it may not seem important, blank lines consciously put
in code can improve readability. The general recommendation is to use blank
lines to separate different logical blocks. When writing code it is useful
to ask ourselves the question "what are the main steps of the algorithm I'm
implementing?". When answered, it gives understanding of how code can be
decomposed into sections. And in order to reflect that they are individual
steps of the algorithm, the corresponding code blocks can be split by blank
lines. Let's consider examples.

Problematic Code
^^^^^^^^^^^^^^^^

.. code-block:: python

    def update_task_state(self, state, state_info=None):
        old_task_state = self.task_ex.state
        if states.is_completed(self.task_ex.state):
            self.notify(old_task_state, self.task_ex.state)
            return
        if not states.is_valid_transition(self.task_ex.state, state):
            return
        child_states = [a_ex.state for a_ex in self.task_ex.executions]
        if state == states.RUNNING and states.PAUSED in child_states:
            return
        self.set_state(state, state_info)
        if states.is_completed(self.task_ex.state):
            self.register_workflow_completion_check()
        self.notify(old_task_state, self.task_ex.state)

Is this method easy to read? The method does a lot of things: it invokes
other methods, checks conditions, calculates values and sets them to variables.
Even more importantly, all of that are different computational steps of the
method. However, they appear in the code one by one without any gaps. So when
a human eye is reading this code there isn't any element in the code that would
tell us where the next step of the algorithm starts. And a blank line can
naturally play a role of such element.

Better Code
^^^^^^^^^^^

.. code-block:: python

    def update_task_state(self, state, state_info=None):
        old_task_state = self.task_ex.state

        if states.is_completed(self.task_ex.state):
            self.notify(old_task_state, self.task_ex.state)

            return

        if not states.is_valid_transition(self.task_ex.state, state):
            return

        child_states = [a_ex.state for a_ex in self.task_ex.executions]

        if state == states.RUNNING and states.PAUSED in child_states:
            return

        self.set_state(state, state_info)

        if states.is_completed(self.task_ex.state):
            self.register_workflow_completion_check()

        self.notify(old_task_state, self.task_ex.state)

Now when we read the method, we clearly see the individual steps:

 - Saving an old task state for further usage
 - Check if task is already completed and if it is, notify clients about it
   and return
 - Check if the state transition we're going to make is valid
 - Calculate state of the child entities
 - Do not proceed with updating the task state if there any running or paused
   child entities
 - Actually update the task state
 - If the task is now completed, schedule the corresponding workflow completion
   check
 - Notify clients about a task transition

Of course, when writing code like this it may be hard to format code this way
in the first place. But once we already have some version of code, we should
take care of people who will surely be reading it in future. After all, the
author may be reading it after some time. Again: programs are read much more
often than written. So we need to make sure our code tells a good story about
what it serves to.

As far as putting a blank line before "if", "try", "for" and "with", the
reasoning is pretty straightforward: all these code flow controls already
reflect separate computational steps because they do something that's
different from the previous command by nature. For example, "if" may route a
program in a different direction at runtime. So all these blocks should be
clearly visible to a reader. "return" is also an outstanding command since it
stops the execution of the current method and gives control back to the caller
of the method. So it also deserves to be well visible.

Using blank lines consciously can also make code more symmetric. That is,
if we don't mix up significantly different commands.

Problematic Code
^^^^^^^^^^^^^^^^

.. code-block:: python

    var1 = "some value"
    my_obj.method1()
    my_obj.method2()
    var2 = "another value"

    ... # The rest of the code snippet

What's wrong with this code? The thing is that we mixed up lines where we do
absolutely different things. Two of them just do set string values to the two
new variables whereas the other two send messages to a different object, i.e.
give it command to do something. In other words, the two lines here are more
abstract than the two others since they don't run any concrete calculation,
it is hidden by method calls against other object. So this code is not
symmetric, it doesn't group commands of similar nature together and it doesn't
separate them from each other.

Better Code
^^^^^^^^^^^

.. code-block:: python

    var1 = "some value"
    var2 = "another value"

    my_obj.method1()
    my_obj.method2()

    ... # The rest of the code snippet

This code fixes the mentioned issues and note that, again, a blank line
clearly communicates that a more abstract block starts and that this block
can and should be maintained separately.


Multi-line Method Calls
-----------------------

Guidelines
^^^^^^^^^^
 - *Long method calls that don't fit into 80 characters must be written down
   in a way that each argument is located on an individual line, as well as
   the closing round bracket.*

All code lines need to be not longer than 80 characters. Once in a while it's
required to break lines when we deal with long instructions. For example, when
we need to write a method call with lots of arguments or the names of the
arguments are long enough so the entire code instruction doesn't fit into
80 characters.

Problematic Code
^^^^^^^^^^^^^^^^

.. code-block:: python

    executor.run_action(self.action_ex.id, self.action_def.action_class,
        self.action_def.attributes or {}, self.action_ex.input,
        self.action_ex.runtime_context.get('safe_rerun', False),
        execution_context, target=target, timeout=timeout)

On many Python projects this way or breaking lines for long method calls
is considered right. However, when we need to read and understand this code
quickly we may experience the following issues:

 - Hard to see where one argument ends and where another one starts
 - Hard to check if the order of arguments is correct
 - If such method call declaration is followed by another code line (e.g.
   another method call) then it's hard to see where the method call
   declaration ends

Better Code
^^^^^^^^^^^

.. code-block:: python

    executor.run_action(
        self.action_ex.id,
        self.action_def.action_class,
        self.action_def.attributes or {},
        self.action_ex.input,
        self.action_ex.runtime_context.get('safe_rerun', False),
        execution_context,
        target=target,
        timeout=timeout
    )

Although the second version of the method call sacrifices conciseness to
some extent, it eliminates the issues mentioned above. Every method argument
is easily visible, it's easy to check the number of the arguments and their
order (e.g. to compare with the method signature) and it's easy to see where
the entire command ends because the ending round bracket on a separate line
communicates it clearly.

