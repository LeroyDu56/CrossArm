%%%
  VERSION:1
  LANGUAGE:ENGLISH
%%%

MODULE Legacy_Palette(SYSMODULE, NOSTEPIN)
  ! Palettisation - réglage opérateur, écrit à la main pour les tests
  CONST robtarget pDepose:=[[100,200,300],[1,0,0,0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]];
  VAR num nCouche:=0;

  proc Depose()
    moveL pDepose, v100, z10, tool0;  ! approche lente
    if nCouche > 2 then
      reset doVentouse;
    endif
    waittime 1.5;
  endproc
ENDMODULE
