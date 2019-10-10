# -*- coding: UTF-8 -*-
from __future__ import absolute_import, unicode_literals
import copy
import six
import behave.parser
import behave.i18n
from behave.step_registry import get_matcher, AmbiguousStep
from behave.runner import the_step_registry
from behave.model_core import TagStatement, Replayable
from behave.textutil import text as _text

""" Extended parser for 'behave.parse.Parser'

    To be monkey-patched onto original one
"""


def alt_parse_feature(data, language=None, filename=None):
    # ALL data operated on by the parser MUST be unicode
    assert isinstance(data, six.text_type)

    try:
        result = AltParser(language).parse(data, filename)
    except behave.parser.ParserError as e:
        e.filename = filename
        raise

    return result


class MacroBlock(TagStatement, Replayable):
    type = 'macro'
    step_type = 'step'

    def __init__(self, filename, line, keyword, name, tags=None, steps=None,
                 description=None):
        tags = tags or []
        super(MacroBlock, self).__init__(filename, line, keyword, name, tags)
        self.description = description or []
        self.steps = steps or []
        # self.feature = None  # REFER-TO: owner=Feature

    def get_formatted_steps(self, params):
        """Return copies of self.steps formatted with parameters
        """
        ret_steps = []
        for orig_step in self.steps:
            new_step = copy.deepcopy(orig_step)
            new_step.reset()
            ret_steps.append(new_step)
            if not params:
                continue
            new_step.name = new_step.name.format(**params)
            if new_step.text:
                new_step.text = new_step.text.format(**params)
            if new_step.table:
                new_step.table.headings[:] = [h.format(**params)
                                              for h in new_step.table.headings]
                for row in new_step.table:
                    row.cells[:] = [c.format(**params) for c in row.cells]
        return ret_steps

    def run(self, context, **kwargs):
        steps = self.get_formatted_steps(kwargs)

        with context._use_with_behave_mode():
            for step in steps:
                passed = step.run(context._runner, quiet=True, capture=False)
                if not passed:
                    # -- ISSUE #96: Provide more substep info to diagnose problem.
                    step_line = u"%s %s" % (step.keyword, step.name)
                    message = "%s SUB-STEP: %s" % \
                              (step.status.name.upper(), step_line)
                    if step.error_message:
                        message += "\nSubstep info: %s\n" % step.error_message
                        message += u"Traceback (of failed substep):\n"
                        message += u"".join(step.exc_traceback)
                    raise AssertionError(message)

        return True



class AltParser(behave.parser.Parser):
    def subaction_detect_taggable_statement(self, line):
        if super(AltParser, self).subaction_detect_taggable_statement(line):
            return True

        macro_kwd = self.match_keyword('macro', line)
        if macro_kwd:
            self._build_macro_statement(macro_kwd, line)
            # body of a Macro is much like a scenario
            self.state = "scenario"
            return True

        return False

    def _build_macro_statement(self, keyword, line):
        name = line[len(keyword) + 1:].strip()
        if self.tags:
            # TODO
            raise NotImplementedError("Tags not supported for %s" % keyword)

        self.statement = MacroBlock(self.filename, self.line,
                                    keyword, name, tags=self.tags)
        add_macro_definition(the_step_registry, self.statement)
        # -- RESET STATE:
        self.tags = []


def add_macro_definition(self, macro):
    step_location = macro.location
    step_type = macro.step_type
    step_text = _text(macro.name)
    step_definitions = self.steps[step_type]
    for existing in step_definitions:
        if self.same_step_definition(existing, step_text, step_location):
            # -- EXACT-STEP: Same step function is already registered.
            # This may occur when a step module imports another one.
            return
        elif existing.match(step_text):     # -- SIMPLISTIC
            message = u"%s has already been defined in\n  existing step %s"
            new_step = u"@%s('%s')" % (step_type, step_text)
            existing.step_type = step_type
            existing_step = existing.describe()
            existing_step += u" at %s" % existing.location
            raise AmbiguousStep(message % (new_step, existing_step))

    mstep = get_matcher(macro.run, step_text)
    mstep._location = macro.location
    step_definitions.append(mstep)

# monkey-patch:
orig_parse_feature = behave.parser.parse_feature
behave.parser.parse_feature = alt_parse_feature

behave.i18n.languages['en']['macro'] = ['Macro']

#eof
