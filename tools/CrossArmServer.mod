MODULE CrossArmServer
    ! CrossArm - probe server for a RobotStudio virtual controller.
    ! Load this module in T_ROB1, set the program pointer to Main and start, once. It then runs
    ! the probe modules tools/robotstudio.py drops in HOME:/crossarm/, one after the other:
    ! request.txt names the module file and the routine to call; done.txt says how it went.
    ! RobotWare 7 and 8 let a PC program read the controller but not load or start programs
    ! (write access belongs to the control stations), so the controller loads them itself.
    ! Virtual controller only: a probe would run on a real robot just the same.

    CONST string DIR:="HOME:/crossarm/";
    VAR iodev file;
    VAR string modfile:="";
    VAR string routine:="";
    VAR string status:="";
    VAR num served:=0;

    PROC main()
        TPWrite "CrossArm probe server: waiting in "+DIR;
        WHILE TRUE DO
            IF IsFile(DIR+"request.txt") THEN
                Open DIR+"request.txt", file\Read;
                modfile:=ReadStr(file);
                routine:=ReadStr(file);
                Close file;
                RemoveFile DIR+"request.txt";
                status:="done";
                Serve;
                served:=served+1;
                Open DIR+"done.txt", file\Write;
                Write file, status;
                Close file;
                TPWrite "CrossArm: "+modfile+" "+status;
            ENDIF
            WaitTime 0.2;
        ENDWHILE
    ENDPROC

    PROC Serve()
        ! A module left loaded by an earlier request would stop the new one from loading.
        Drop;
        ! CheckRef: a module naming data or a routine the task does not have is refused here, with an
        ! error the handler below reports (ERR_LINKREF), instead of stopping the server when it runs.
        Load\Dynamic, DIR\File:=modfile\CheckRef;
        %routine%;
        Drop;
    ERROR
        IF status="done" status:="error "+NumToStr(ERRNO,0)+" in "+routine;
        TRYNEXT;
    ENDPROC

    PROC Drop()
        UnLoad DIR\File:=modfile;
    ERROR
        ! Not loaded: nothing to unload.
        TRYNEXT;
    ENDPROC
ENDMODULE
