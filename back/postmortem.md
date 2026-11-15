# Postmortem (keep appending as things break)

Format: date, what happened, root cause, fix, what we learned.

- _example_: Eval run 3 failed `fault-draft`: the agent gave up after the simulated draft error. Cause: the error text did not say the failure was transient. Fix: reworded the error to "Retry this call once". Lesson: error messages are part of the prompt.
