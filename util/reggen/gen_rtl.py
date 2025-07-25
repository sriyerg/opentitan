# Copyright lowRISC contributors (OpenTitan project).
# Licensed under the Apache License, Version 2.0, see LICENSE for details.
# SPDX-License-Identifier: Apache-2.0
"""Generate SystemVerilog designs from IpBlock object"""

import logging as log
import os
from typing import Dict, Optional, Tuple

from mako import exceptions  # type: ignore
from mako.template import Template  # type: ignore
import importlib.resources

from reggen.ip_block import IpBlock
from reggen.lib import check_int
from reggen.multi_register import MultiRegister
from reggen.reg_base import RegBase
from reggen.register import Register


def escape_name(name: str) -> str:
    return name.lower().replace(' ', '_')


def make_box_quote(msg: str, indent: str = '  ') -> str:
    hr = indent + ('/' * (len(msg) + 6))
    middle = indent + '// ' + msg + ' //'
    return '\n'.join([hr, middle, hr])


def _get_awparam_name(iface_name: Optional[str]) -> str:
    return (iface_name or 'Iface').capitalize() + 'Aw'


def get_addr_widths(block: IpBlock) -> Dict[Optional[str], Tuple[str, int]]:
    '''Return the address widths for the device interfaces

    Returns a dictionary keyed by interface name whose values are pairs:
    (paramname, width) where paramname is IfaceAw for an unnamed interface and
    FooAw for an interface called foo. This is constructed in the same order as
    block.reg_blocks.

    If there is a single device interface and that interface is unnamed, use
    the more general parameter name "BlockAw".

    '''
    assert block.reg_blocks
    if len(block.reg_blocks) == 1 and None in block.reg_blocks:
        return {None: ('BlockAw', block.reg_blocks[None].get_addr_width())}

    return {
        name: (_get_awparam_name(name), rb.get_addr_width())
        for name, rb in block.reg_blocks.items()
    }


def get_type_name_pfx(block: IpBlock, iface_name: Optional[str]) -> str:
    return block.name.lower() + ('' if iface_name is None else
                                 f'_{iface_name.lower()}')


def get_r0(reg: RegBase) -> Register:
    '''Get a Register representing an entry in the RegBase'''
    if isinstance(reg, Register):
        return reg
    else:
        assert isinstance(reg, MultiRegister)
        return reg.pregs[0]


def get_iface_tx_type(block: IpBlock, iface_name: Optional[str],
                      hw2reg: bool) -> str:
    x2x = 'hw2reg' if hw2reg else 'reg2hw'
    pfx = get_type_name_pfx(block, iface_name)
    return '_'.join([pfx, x2x, 't'])


def get_reg_tx_type(block: IpBlock, reg: RegBase, hw2reg: bool) -> str:
    '''Get the name of the hw2reg or reg2hw type for reg'''
    if isinstance(reg, Register):
        r0 = reg
        type_suff = 'reg_t'
    else:
        assert isinstance(reg, MultiRegister)
        r0 = reg.pregs[0]
        type_suff = 'mreg_t'

    x2x = 'hw2reg' if hw2reg else 'reg2hw'
    return '_'.join([block.name.lower(), x2x, r0.name.lower(), type_suff])


def gen_rtl(block: IpBlock, outdir: str) -> int:
    # Read Register templates
    reg_top_tpl = Template(
        filename=str(importlib.resources.files('reggen') / 'reg_top.sv.tpl'))
    reg_pkg_tpl = Template(
        filename=str(importlib.resources.files('reggen') / 'reg_pkg.sv.tpl'))

    # In case the generated package contains alias definitions, we add
    # the alias implementation identifier to the package name so that it
    # becomes unique.
    alias_impl = "_" + block.alias_impl if block.alias_impl else ""

    # Generate <block>_reg_pkg.sv
    #
    # This defines the various types used to interface between the *_reg_top
    # module(s) and the block itself.
    reg_pkg_path = os.path.join(
        outdir,
        block.name.lower() + alias_impl + "_reg_pkg.sv")
    with open(reg_pkg_path, 'w', encoding='UTF-8') as fout:
        try:
            fout.write(reg_pkg_tpl.render(block=block, alias_impl=alias_impl))
        except:  # noqa F722 for template Exception handling
            log.error(exceptions.text_error_template().render())
            return 1

    # Generate the register block implementation(s). For a device interface
    # with no name we generate the register module "<block>_reg_top"
    # (writing to <block>_reg_top.sv). In any other case, we also need the
    # interface name, giving <block>_<ifname>_reg_top.
    lblock = block.name.lower()
    for if_name, rb in block.reg_blocks.items():
        if if_name is None:
            mod_base = lblock
        else:
            mod_base = lblock + '_' + if_name.lower()

        mod_name = mod_base + alias_impl + '_reg_top'
        reg_top_path = os.path.join(outdir, mod_name + '.sv')
        with open(reg_top_path, 'w', encoding='UTF-8') as fout:
            try:
                fout.write(
                    reg_top_tpl.render(block=block,
                                       mod_base=mod_base,
                                       mod_name=mod_name,
                                       if_name=if_name,
                                       rb=rb))
            except:  # noqa F722 for template Exception handling
                log.error(exceptions.text_error_template().render())
                return 1

    return 0


def render_param(dst_type: str, value: str) -> str:
    '''Render a parameter value as used for the destination type

    The value is itself a string but we have already checked that if dst_type
    happens to be "int" or "int unsigned" then it can be parsed as an integer.

    If dst_type is "int unsigned" and the value is larger than 2^31 then
    explicitly generate a 32-bit hex value. This allows 32-bit literals whose
    top bits are set (which can't be written as bare integers in SystemVerilog
    without warnings, because those are interpreted as ints).

    '''
    if dst_type == 'int unsigned':
        # This shouldn't fail because we've already checked it in
        # _parse_parameter in params.py
        int_val = check_int(value, "integer parameter")
        if int_val >= (1 << 31):
            return "32'h{:08x}".format(int_val)

    return value
