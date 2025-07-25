// Copyright lowRISC contributors (OpenTitan project).
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0
//
// Register slice conforming to Comportability guide.

module prim_subreg_ext #(
  parameter int unsigned DW = 32
) (
  input          re,
  input          we,
  input [DW-1:0] wd,

  input [DW-1:0] d,

  // output to HW and Reg Read
  output logic          qe,
  output logic          qre,
  output logic [DW-1:0] q,
  output logic [DW-1:0] ds,
  output logic [DW-1:0] qs
);

  // for external registers, there is no difference
  // between qs and ds
  assign ds = d;
  assign qs = d;
  assign q = wd;
  assign qe = we;
  assign qre = re;

endmodule
