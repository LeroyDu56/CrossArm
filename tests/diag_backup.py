# SPDX-FileCopyrightText: 2026 Enzo LEROY
# SPDX-License-Identifier: BUSL-1.1

"""A small ABB backup written for testing `crossarm diagnose`: BACKINFO (backinfo.txt, system.xml), a program and
a system module, EIO.cfg. Written into a test's folder by `make_backup`: kept out of tests/fixtures, where its
RAPID folder would be taken for the backup of the tests converting tests/fixtures/rapid."""

from pathlib import Path

FILES = {
    "BACKINFO/backinfo.txt": """\
#
# Generated backup file, do not edit.
#
# Originally at: /hd0a/BACKUP/GLAZING_CELL_7_BACKUP
# 2026-03-14  08:41:27
#
>>SYSTEM_ID:
2400-551908

>>PRODUCTS_ID:
RobotOS Version: 18.1.0
RobotWare Version: 6.14.02
Robots Version: 6.14.02

  RobotWare Base
  English
  709-1 DeviceNet Master/Slave
  623-1 Multitasking
  Glazing line options by Vandermeer Automation
  IRB 2400-16/1.55

>>TASK1: (T_GLAZE,,)
""",
    "BACKINFO/system.xml": """\
<?xml version="1.0" encoding="utf-8"?>
<!-- Written for testing: an XML system description, read loosely by crossarm.rapid.system_info. -->
<System>
  <SystemName>GlazingCellSeven</SystemName>
  <SerialNumber>2400-551908</SerialNumber>
  <Owner>Vandermeer Automation, plant 42</Owner>
  <Products>
    <Product name="RobotWare" version="6.14.02.00"/>
  </Products>
  <Options>
    <Option name="616-1 PC Interface"/>
    <Option name="608-1 World Zones"/>
    <Option name="Vandermeer glazing pack"/>
  </Options>
</System>
""",
    "RAPID/TASK1/PROGMOD/GlazeMain.mod": """\
MODULE GlazeMain
  ! Glazing cell 7, line Vandermeer, written for testing
  RECORD paneSpec
    num paneWidthMm;
    num paneHeightMm;
    string paneSupplier;
  ENDRECORD

  CONST robtarget pPaneCorner := [[1287.45,-342.18,915.6],[0.70711,0,0.70711,0],[0,-1,0,0],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
  CONST jointtarget jParkGlazer := [[12.5,-27.75,33,0,64.25,-118],[9E+09,9E+09,9E+09,9E+09,9E+09,9E+09]];
  PERS tooldata tGlueNozzle := [TRUE,[[18.4,0,236.75],[1,0,0,0]],[3.75,[0,0,92],[1,0,0,0],0,0,0]];
  PERS wobjdata wobjGlazeTable := [FALSE,TRUE,"",[[640,-1180,455],[1,0,0,0]],[[0,0,0],[1,0,0,0]]];
  VAR paneSpec specKwartel := [1650,980,"Saint Brandaris"];
  VAR num beadCounter := 0;
  VAR num beadLengths{24};
  PERS string lastOperatorZwaluw := "Hendrika";

  PROC main()
    ! start the Zwaluw glazing cycle
    WHILE TRUE DO
      glazePane specKwartel.paneWidthMm, pPaneCorner;
      IF beadCounter > 4321 THEN
        TPWrite "Replace cartridge Brandaris 77";
        beadCounter := 0;
      ENDIF
    ENDWHILE
  ENDPROC

  PROC glazePane(num widthMm, robtarget corner)
    MoveJ Offs(corner, 0, 0, 150), v1000, z50, tGlueNozzle\\WObj:=wobjGlazeTable;
    SetDO doGlueValve, 1;
    FOR stripeIdx FROM 1 TO 4 DO
      MoveL Offs(corner, widthMm, 0, 0), v250, fine, tGlueNozzle\\WObj:=wobjGlazeTable;
      beadLengths{stripeIdx} := widthMm * 0.9375;
    ENDFOR
    SetDO doGlueValve, 0;
    WaitDI diPaneSeated, 1;
    beadCounter := beadCounter + 1;
    SetGO goRecipeKwartel, 23;
    MoveAbsJ jParkGlazer, v500, z10, tGlueNozzle;
  ERROR
    IF ERRNO = ERR_WAIT_MAXTIME THEN
      TPWrite "Pane missing at Brandaris";
      RETRY;
    ENDIF
  ENDPROC

  FUNC num paneArea(paneSpec spec)
    RETURN spec.paneWidthMm * spec.paneHeightMm;
  ENDFUNC
ENDMODULE
""",
    "RAPID/TASK1/SYSMOD/CellData.sys": """\
MODULE CellData(SYSMODULE)
  ! Vandermeer cell data, written for testing
  PERS num nGlazeSpeedMmS := 87;
  PERS string sPlantCode := "NL-Zaandam-0457";
ENDMODULE
""",
    "SYSPAR/EIO.cfg": """\
EIO:CFG_1.0:6:1::
#
INDUSTRIAL_NETWORK:

      -Name "DeviceNet" -Label "DeviceNet Master/Slave Network" -Address "2"
#
DEVICENET_DEVICE:

      -Name "dnGlazer" -VendorName "ABB Robotics" -ProductName "DSQC 652 24 VDC I/O Device"\\
      -Label "Glazing head board" -Address "17" -VendorId 75 -ProductCode 26 -DeviceType 7
#
EIO_SIGNAL:

      -Name "doGlueValve" -SignalType "DO" -Device "dnGlazer" -DeviceMap "13"\\
      -Label "Glue valve station 38"

      -Name "diPaneSeated" -SignalType "DI" -Device "dnGlazer" -DeviceMap "11"

      -Name "goRecipeKwartel" -SignalType "GO" -Device "dnGlazer" -DeviceMap "16-23"

      -Name "aoBeadFlow" -SignalType "AO" -Device "dnGlazer" -DeviceMap "32-47"
""",
}


def make_backup(folder: Path) -> Path:
    """The backup, written in `folder`/diag_backup; returns its folder."""
    root = folder / "diag_backup"
    for name, text in FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root
