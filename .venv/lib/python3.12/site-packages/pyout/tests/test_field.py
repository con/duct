# -*- coding: utf-8 -*-
import pytest

from pyout.field import Field
from pyout.field import Nothing
from pyout.field import StyleProcessors


def test_field_base():
    assert Field()("ok") == "ok        "
    assert Field(width=5, align="right")("ok") == "   ok"


def test_field_update():
    field = Field()
    field.width = 2
    assert field("ok") == "ok"


def test_field_processors():
    def pre(_, result):
        return result.upper()

    def post1(_, result):
        return "AAA" + result

    def post2(_, result):
        return result + "ZZZ"

    field = Field(width=6, align="center",
                  default_keys=["some_key", "another_key"])
    field.add("pre", "some_key", pre)
    field.add("post", "another_key", *[post1, post2])
    assert field("ok") == "AAA  OK  ZZZ"

    with pytest.raises(ValueError):
        field.add("not pre or post", "k")

    with pytest.raises(ValueError):
        field.add("pre", "not registered key")


@pytest.mark.parametrize("text",
                         ["", "-", "…"],
                         ids=["text=''", "text='-'", "text='…'"])
def test_something_about_nothing(text):
    nada = Nothing(text=text)
    assert not nada

    assert str(nada) == text
    assert "{:5}".format(nada) == "{:5}".format(text)
    assert "x" + nada == "x" + text
    assert nada + "x" == text + "x"


def test_style_processor_render():
    sp = StyleProcessors()
    with pytest.raises(NotImplementedError):
        sp.render("key", "value")
