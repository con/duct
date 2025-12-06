"""Not much of an interface for styling tabular terminal output.

This module defines a mostly useless Tabular entry point.  Previous lines are
not updated, and the results are not styled (e.g., no coloring or bolding of
values).  In other words, this is not a real attempt to support Windows.
"""

from pyout import interface


class NoUpdateTerminalStream(interface.Stream):

    def __init__(self, stream=None, interactive=None):
        super(NoUpdateTerminalStream, self).__init__(
            stream=stream, interactive=interactive)
        self.supports_updates = False

    def _die(self, *args, **kwargs):
        raise NotImplementedError("{!s} does not support 'update' methods"
                                  .format(self.__class__.__name__))

    clear_last_lines = _die
    overwrite_line = _die
    move_to = _die

    # Height and width are the fallback defaults of py3's
    # shutil.get_terminal_size().

    @property
    def width(self):
        return 80

    @property
    def height(self):
        return 24

    def write(self, text):
        self.stream.write(text)


class Tabular(interface.Writer):
    """Like `pyout.tabular.Tabular`, but broken.

    This doesn't support terminal styling or updating previous content.
    """

    def __init__(self, columns=None, style=None, stream=None,
                 interactive=None, mode=None, continue_on_failure=True,
                 wait_for_top=3, max_workers=None):
        super(Tabular, self).__init__(
            columns, style, stream=stream,
            interactive=interactive, mode=mode,
            continue_on_failure=continue_on_failure,
            wait_for_top=wait_for_top, max_workers=max_workers)
        streamer = NoUpdateTerminalStream(
            stream=stream, interactive=interactive)
        super(Tabular, self)._init(style, streamer)
