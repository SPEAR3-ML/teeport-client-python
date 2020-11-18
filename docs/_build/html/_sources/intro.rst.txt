Motivation
==========

The Wall
--------

There's a wall between the optimization algorithm and problem when:

- They are written in different language

  - i.e. algorithm in `python` and problem in `matlab`
  
- They are located at different place and can't be easily put together

  - i.e. remote optimization due to COVID-19
  
- The policy doesn't allow the environment configurations that are needed for the algorithm/problem

  - i.e. The strict policy in the accelerator control rooms

Even within the algorithm there could be a wall: imagine that you want to use some python modules in your matlab algorithm.

Break the Wall
--------------

Calling one language script/function within another language script/function is
cumbersome and sometimes not feasible. Translating the code to the target 
language usually requires expert skills and lots of attention, energy and time.
Besides, the translation process is highly error-prone. Use an implementation that already exists is risky from time to time. The way to go is breaking the wall.

Introducing Teeport.

Concepts
========

Before officially introduce Teeport, let's have a look at the basic concepts/terms used frequently in a Teeport context: `Evaluator`_, `Optimizer`_, `Processor`_ and `Monitor`_.

Evaluator
---------

An implementation of a optimization problem. Usually can be abstracted as a function:

.. code-block:: python

    Y = evaluate(X, configs)

Where the ``configs`` variable is the configuration of the problem, say:

.. code-block:: python

    configs = {
        'noise_level': 0.1,  # emulate the experimental env
        'wall_time': 1,  # emulate the experimental env
        ...
    }

Optimizer
---------

An implementation of an optimization algorithm:

.. code-block:: python

    x_best = optimize(evaluate, configs)

The ``evaluate`` variable is the target function to be optimized:

.. code-block:: python

    Y = evaluate(X)

An example of ``configs``:

.. code-block:: python

    configs = {
        'D': 8, # dimension of the problem to be optimized
        'N': 300, # maximum iterations
        ...
    }

Processor
---------

A function that processes data and return the processed result:

.. code-block:: python

    result = process(data, configs)

An example of ``configs``:

.. code-block:: python

    configs = {
        'return_grad': False,
        'ard': True,
        ...
    }

Monitor
-------

A visualization of the data flow between the `Optimizer`_ and the `Evaluator`_ that catches some feature of the data.

.. image:: ./images/monitor.png
    :alt: evaluation history monitor

Philosophy of Teeport
=====================

Teeport is designed to break the wall between the optimization algorithms and problems.

.. image:: ./images/teeport-idea.png
    :alt: idea behind teeport
    :width: 80 %
    :align: center