// Copyright lowRISC contributors (OpenTitan project).
// Licensed under the Apache License, Version 2.0, see LICENSE for details.
// SPDX-License-Identifier: Apache-2.0

class hmac_env_cfg extends cip_base_env_cfg #(.RAL_T(hmac_reg_block));
  `uvm_object_utils(hmac_env_cfg)

  // A flag to notify scoreboard if digest is corrupted by wipe_secret command.
  bit wipe_secret_triggered;

  // Flag to notify stress_all_with_rand_reset task that hash_process command is triggered.
  // This would help trying to issue reset at specific timing during hmac hashing.
  bit hash_process_triggered;

  // Randomization knob that controls how often an opportunity for save and restore is taken.  'Save
  // and restore' means that on a complete block, we stop hashing, read the digest and message
  // length via CSRs, disable SHA, write digest and message length back via CSRs, re-enable SHA and
  // continue hashing.
  int save_and_restore_pct;

  // Flag to notify the scoreboard to treat the current digest as NIST
  bit is_nist_test = 0;

  // TODO (#23562): will be removed when tackling this issue
  // Flag to notify the scoreboard to skip the current message writes and don't flush its variables
  bit sar_skip_ctxt = 0;

  hmac_vif hmac_vif;

  // Standard SV/UVM methods
  extern function new(string name="");

  // Class specific methods
  extern function void initialize(bit [TL_AW-1:0] csr_base_addr = '1);
endclass : hmac_env_cfg


function hmac_env_cfg::new(string name="");
  super.new(name);
endfunction : new

function void hmac_env_cfg::initialize(bit [TL_AW-1:0] csr_base_addr = '1);
  list_of_alerts = hmac_env_pkg::LIST_OF_ALERTS;
  super.initialize(csr_base_addr);
  // set num_interrupts & num_alerts which will be used to create coverage and more
  num_interrupts = ral.intr_state.get_n_used_bits();

  // only support 1 outstanding TL items in tlul_adapter
  m_tl_agent_cfg.max_outstanding_req = 1;

  // Used to allow reset operations without waiting for CSR accesses to complete
  can_reset_with_csr_accesses = 1;

  void'($value$plusargs("is_nist_test=%b", is_nist_test));
endfunction : initialize
