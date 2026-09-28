MODULE ElbowProbe
    ! CrossArm - arm configuration probe. Run PROC ProbeElbow (no motion):
    ! it writes the confdata, TCP position and orientation computed for each
    ! joint set to HOME:/elbowprobe.txt
    !  1: J3 60
    !  2: J3 -60
    !  3: J3 -75
    !  4: J3 -80
    !  5: J3 -81.5
    !  6: J3 -82.2
    !  7: J3 -85
    !  8: J3 -90
    !  9: J3 -120
    ! 10: J3 -150
    ! 11: J2 +40 J3 -100
    ! 12: J2 -60 J3 -100
    CONST jointtarget JT{12}:=[
        [[0,0,60,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
        [[0,0,-60,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
        [[0,0,-75,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
        [[0,0,-80,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
        [[0,0,-81.5,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
        [[0,0,-82.2,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
        [[0,0,-85,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
        [[0,0,-90,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
        [[0,0,-120,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
        [[0,0,-150,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
        [[0,40,-100,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]],
        [[0,-60,-100,0,90,0],[9E9,9E9,9E9,9E9,9E9,9E9]]];

    PROC ProbeElbow()
        ! The file is closed after every point: an error keeps what was already written.
        VAR iodev f;
        VAR robtarget p;
        VAR num nPoint:=0;
        Open "HOME:" \File:="elbowprobe.txt", f \Write;
        Close f;
        FOR i FROM 1 TO Dim(JT,1) DO
            nPoint:=i;
            TPWrite "Probe point "\Num:=i;
            p:=CalcRobT(JT{i},tool0\WObj:=wobj0);
            Open "HOME:" \File:="elbowprobe.txt", f \Append;
            Write f, NumToStr(i,0)+" "+ValToStr(p.robconf)+" "+ValToStr(JT{i}.robax);
            Write f, NumToStr(i,0)+" trans "+NumToStr(p.trans.x,3)+" "+NumToStr(p.trans.y,3)+" "+NumToStr(p.trans.z,3);
            Write f, NumToStr(i,0)+" rot "+NumToStr(p.rot.q1,6)+" "+NumToStr(p.rot.q2,6)+" "+NumToStr(p.rot.q3,6)+" "+NumToStr(p.rot.q4,6);
            Close f;
        ENDFOR
        TPWrite "elbowprobe.txt written in HOME:";
        ! Stop here: in continuous run mode main would restart and rewrite the file.
        Stop;
    ERROR
        TPWrite "Probe error at point "\Num:=nPoint;
        TPWrite "ERRNO = "\Num:=ERRNO;
        Stop;
    ENDPROC
ENDMODULE
