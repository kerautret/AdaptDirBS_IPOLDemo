"""
Demonstration of paper: Adaptive Directional Tracking of Blurred Segments
demo editor: Bertrand Kerautret
"""



from lib import base_app, build, http, image
from lib.misc import   ctime
from lib.base_app import init_app
from lib.config import cfg_open
import shutil
import cherrypy
from cherrypy import TimeoutError
import os.path
import time
from PIL import Image
import ImageDraw


class app(base_app):
    """ Adaptive Directional Tracking of Blurred Segments """

    title = 'Adaptive Directional Tracking of Blurred Segments'
    xlink_article = 'http://www.ipol.im/'
    xlink_src =  'https://github.com/evenp/FBSD/archive/master.tar.gz'
    demo_src_filename  = 'master.tar.gz'
    pensize = 3
    input_nb = 1
    input_max_pixels = 512 * 512        # max size (in pixels) of input image
    input_max_weight = 10 * 512 * 512 # max size (in bytes) of input file
    input_dtype = '3x8i'                # input image expected data type
    input_ext = '.png'                  # expected extension
    is_test = True       # switch to False for deployment
    default_param = {'width': 3,  # default parameters
                     'minsize': 15,  # default parameters
                     'pensize': pensize,
                     'pencolor':'red'}
    pencolors = {'red'   : [255, 0, 0],'green'   : [0, 255, 0]}
    list_commands = ""
    hasAtLeastOneMarker = False
    mode_select_marker = 'seeds'
    sizeSeeds = 0
    
    def __init__(self):
        """
        App setup
        """
        # Setup the parent class
        base_dir = os.path.dirname(os.path.abspath(__file__))
        base_app.__init__(self, base_dir)

        # Select the base_app steps to expose
        # index() and input_xxx() are generic
        base_app.index.im_func.exposed = True
        base_app.input_select.im_func.exposed = True
        base_app.input_upload.im_func.exposed = True
        # params() is modified from the template
        base_app.params.im_func.exposed = True
        # result() is modified from the template
        base_app.result.im_func.exposed = True
        # Generate a new timestamp
        self.timestamp = int(100*time.time())


    def getSeedsSize(self):
        list = self.readcommandlist()
        nb = 0 
        for (t, x, y) in list:
            if t == 'seeds' :
                nb = nb + 1
        return nb
    
        
    def build(self):
        """
        program build/update
        """
        # store common file path in variables
        tgz_file = self.dl_dir + self.demo_src_filename
        prog_names = ["ipolDemo"]
        script_names =  ["convert.sh", "displaySegments.sh", "displaySegmentsInteract.sh"]
        prog_bin_files = []


        
        
        for f in prog_names:
            prog_bin_files.append(self.bin_dir+ f)

        log_file = self.base_dir + "build.log"
        # get the latest source archive
        build.download(self.xlink_src, tgz_file)
        # test if the dest file is missing, or too old
        if (os.path.isfile(prog_bin_files[0])
            and ctime(tgz_file) < ctime(prog_bin_files[0])):
            cherrypy.log("not rebuild needed",
                         context='BUILD', traceback=False)
        else:
            # extract the archive
            build.extract(tgz_file, self.src_dir)

            # build the program
            build.run("cd %s; qmake ; make " %(self.src_dir+"FBSD-master/IPOLdemo"), stdout=log_file)
            
            # save into bin dir
            if os.path.isdir(self.bin_dir):
                shutil.rmtree(self.bin_dir)
            os.mkdir(self.bin_dir)

            for i in range(0, len(prog_bin_files)) :
                shutil.copy(self.src_dir + os.path.join("FBSD-master/IPOLdemo", \
                            prog_names[i]), prog_bin_files[i])

            for f in script_names :
                shutil.copy(self.src_dir + os.path.join("FBSD-master/IPOLdemo/Scripts", f), \
                            self.bin_dir)
            
            # cleanup the source dir
            shutil.rmtree(self.src_dir)

        return


    #
    # PARAMETER HANDLING
    #

    def readcommandlist(self):
        """
        Read the drawing commandlist from maskcomands.txt
        """

        try:
            ifile = file(self.work_dir + 'maskcommands.txt', 'r')
            commandlist = [(line.split(' ')[0], int(line.split(' ')[1]), int(line.split(' ')[2])) \
                for line in ifile.readlines()]

            ifile.close()
        except IOError:
            commandlist = []

        return commandlist


    def rendermask(self):
        """
        Render the drawing commandlist into the mask
        """
        
        commandlist = self.readcommandlist()
        size = image(self.work_dir + 'input_0.png').size
        self.cfg['param']['viewbox_width'] = size[0]
        self.cfg['param']['viewbox_height'] = size[1]
        self.hasAtLeastOneMarker = not (not commandlist)
        mask = Image.new('P', size, 0)   # Create a grayscale image
        draw = ImageDraw.Draw(mask)
        
        outSeeds = open(self.work_dir + 'seeds.dat', 'w')
        outTips = open(self.work_dir + 'tips.dat', 'w')
        self.sizeSeeds = 0
        # need to recompute when user change param from an initial expe

        lastx = 0
        lasty = 0
        for (t, x, y) in commandlist:
            if t == 'seeds' :
               draw.ellipse((x - self.pensize, y - self.pensize, x + self.pensize + 1, y + self.pensize + 1), fill=255)
               outSeeds.write(str(x)+" "+str(size[1]-y)+" ")
            if t == 'tips' :
               draw.ellipse((x - self.pensize, y - self.pensize, x + self.pensize + 1, y + self.pensize + 1), fill=254)
               outTips.write(str(x)+","+str(size[1]-y)+",")
            if self.sizeSeeds % 2 == 1  :
                draw.line((lastx, lasty, x, y), fill=254)
                outSeeds.write("\n")
            self.sizeSeeds = self.sizeSeeds + 1
            lastx = x
            lasty = y
        outSeeds.close()
        outTips.close()
        mask.putpalette([128, 128, 128] + [0, 0, 0]*253
                        + self.pencolors['red']+self.pencolors['green'])       
        mask.save(self.work_dir + 'mask.gif', transparency=0)
        self.cfg['param']['sizeSeeds'] = self.sizeSeeds
      


    @cherrypy.expose
    @init_app
    def editmask(self, **kwargs):
        """
        Edit the inpainting mask
        """

        generate_options = {
            'random text' : 'text',
            'random dots' : 'dots:3',
            'random scribble' : 'scribble:3',
            'random Bernoulli' : 'Bernoulli:0.5'
            }
        commandlist = self.readcommandlist()

        if 'action' in kwargs:
            if kwargs['action'] == 'undo':
                if commandlist:
                    commandlist.pop()
            elif kwargs['action'] == 'clear':
                commandlist = []
            elif kwargs['action'] == 'enter seeds':
                self.mode_select_marker = 'seeds'
            elif kwargs['action'] == 'enter tips':
                self.mode_select_marker = 'tips'
                
            elif kwargs['action'] in generate_options.keys():
                self.wait_proc(self.run_proc(['randmask',
                    generate_options[kwargs['action']],
                    self.work_dir + 'input_0.png', 'mask.png'],
                    stdout=None, stderr=None), None)

                if os.path.isfile(self.work_dir + 'maskcommands.txt'):
                    os.remove(self.work_dir + 'maskcommands.txt')

                mask = Image.open(self.work_dir + 'mask.png')
                mask = mask.convert('L')
                mask = mask.convert('P')
                mask.putpalette([128, 128, 128] + [0, 0, 0]*254
                    + self.pencolors[self.cfg['param']['pencolor']])
                mask.save(self.work_dir + 'mask.gif', transparency=0)

                return self.tmpl_out('params.html')
  
        else:
            commandlist.append((self.mode_select_marker, \
                int(kwargs['x']), int(kwargs['y'])))

        f = file(self.work_dir + 'maskcommands.txt', 'w')

        f.writelines('%s %i %i\n' % (t, x, y)  \
                    for (t, x, y) in commandlist )
        f.close()

        # Generate a new timestamp
        self.timestamp = int(100*time.time())
        self.cfg['param']['pensize'] = self.pensize
        # Set undefined parameters to default values
        self.cfg['param'] = dict(self.default_param, **self.cfg['param'])
        self.rendermask()
        return self.tmpl_out('params.html')


    @cherrypy.expose
    @init_app
    def params(self, newrun=False, msg=None):
        """
        Configure the algo execution
        """
        if newrun:
            old_work_dir = self.work_dir
            self.clone_input()
            # Keep old parameters
            self.cfg['param'] = cfg_open(old_work_dir
                + 'index.cfg', 'rb')['param']
            # Also need to clone maskcommands.txt to keep the mask
            if os.path.isfile(old_work_dir + 'maskcommands.txt'):
                shutil.copy(old_work_dir + 'maskcommands.txt',
                    self.work_dir + 'maskcommands.txt')

        # Set undefined parameters to default values
        self.cfg['param'] = dict(self.default_param, **self.cfg['param'])
        # Generate a new timestamp
        self.timestamp = int(100*time.time())
        self.rendermask()
        return self.tmpl_out('params.html')


    @cherrypy.expose
    @init_app
    def wait(self, **kwargs):
        """
        Run redirection
        """

        # Read webpage parameters from kwargs, but only those that
        # are defined in the default_param dict.  If a parameter is not
        # defined by kwargs, the value from default_param is used.
        self.cfg['param'] = dict(self.default_param.items() +
            [(p,kwargs[p]) for p in self.default_param.keys() if p in kwargs])

        self.cfg['param']['negate'] = 'negate' in kwargs

        # Open image and inpainting domain mask
        img = Image.open(self.work_dir + 'input_0.png').convert('RGB')
        mask = Image.open(self.work_dir + 'mask.gif')

        # Extract alpha
        alpha = mask.copy()
        alpha.putpalette([0, 0, 0]*255 + [255, 255, 255])
        alpha = alpha.convert('L')

        # Extract mask palette for display
        lut = mask.resize((256, 1))
        lut.putdata(range(256))
        lut = lut.convert('RGB').getdata()

        # Save binary PNG version of the mask
        mask.putpalette([0, 0, 0]*255 + [255, 255, 255])
        mask.save(self.work_dir + 'mask.png')

        # Save image + mask composited version for display
        img.paste(lut[255], alpha)
        img.save(self.work_dir + 'composite.png')

        # Save another composite where mask is gray for computation
        img.paste((128, 128, 128), alpha)
        img.save(self.work_dir + 'u0.png')

        # Generate a new timestamp
        self.timestamp = int(100*time.time())
        http.refresh(self.base_url + 'run?key=%s' % self.key)
        return self.tmpl_out("wait.html")

        # Export the seeds files
        
        
    

    @cherrypy.expose
    @init_app
    def run(self):
        """
        Algorithm execution
        """
        # Run the algorithm
        stdout = open(self.work_dir + 'stdout.txt', 'w')
        self.list_commands = ""
        self.sizeSeeds = self.getSeedsSize()
        try:
            run_time = time.time()
            self.run_algo(stdout=stdout)
            self.cfg['info']['run_time'] = time.time() - run_time
        except TimeoutError:
            return self.error(errcode='timeout')
        except RuntimeError:
            print "Run time error"
            return self.error(errcode='runtime')

        stdout.close()
        http.redir_303(self.base_url + 'result?key=%s' % self.key)

        # Archive
        if self.cfg['meta']['original']:
            ar = self.make_archive()
            ar.add_file("input_0.png",
                info="original image")
            ar.add_file("resultLines.png",
                info="result lines")
#            ar.add_file("commands.txt", info="commands")
            ar.add_info({"width":  int(self.cfg['param']['width'])})
            ar.add_info({"min size":  int(self.cfg['param']['minsize'])})
            ar.add_info({"version": self.cfg['param']["version"]})
            ar.save()

        return self.tmpl_out("run.html")


    def run_algo(self, stdout=None):
        """
        The core algo runner
        could also be called by a batch processor
        this one needs no parameter
        """
        
        # # Get image size
        size = image(self.work_dir + 'input_0.png').size
        ##  -------
        ## process 1: transform input file
        ## ---------
        command_args = ['convert.sh', 'input_0.png', 'inputNG.pgm']
        self.runCommand(command_args)
        command_args = ['convert.sh', 'inputNG.pgm', 'input.ppm']
        self.runCommand(command_args)

        ##  -------
        ## process 2: apply the line detection algorithm
        ## ---------

        inputWidth = image(self.work_dir + 'input_0.png').size[0]
        inputHeight = image(self.work_dir + 'input_0.png').size[1]
        if self.sizeSeeds == 0 :            
            command_args = ['ipolDemo'] + \
                           [ 'inputNG.pgm',  "outputContours.txt",  str(self.cfg['param']['width']), str(self.cfg['param']['minsize']) ]
        else :
            command_args = ['ipolDemo'] + \
                           [ 'inputNG.pgm',  "outputContours.txt",  str(self.cfg['param']['width']), str(self.cfg['param']['minsize']), "seeds.dat"]
        
        
        
        f = open(self.work_dir+"algoLog.txt", "a")
        cmd = self.runCommand(command_args, None, f)
        f.close()
        
        ##  -------
        ## process 2 bis: apply the line detection algorithm
        ## ---------
        if self.sizeSeeds == 0 : 
            command_args = ['displaySegments.sh'] + \
                           [ 'input.ppm',  "outputContours.txt", 'resultLines']
        else:
            command_args = ['displaySegmentsInteract.sh'] + \
                           [ 'input.ppm',  "outputContours.txt", "seeds.dat", 'resultLines']
            
        f = open(self.work_dir+"algoLogBis.txt", "a")
        cmd = self.runCommand(command_args, None, f)
        f.close()


        ## ---------
        ## process 3: converting to output result
        ## ---------
        widthDisplay = max(inputWidth, 512)
        fInfo = open(self.work_dir+"algoLog.txt", "a")
        command_args = ['convert.sh', '-background', '#FFFFFF', '-flatten', \
                        self.work_dir +'resultLines.eps', '-geometry', str(widthDisplay)+"x", 'resultLines.png']
        self.runCommand(command_args, None, fInfo)


        #self.runCommand(command_args,stdOut=stdout, stdErr=stdout)

        # command_args = ['convert.sh', 'mask.png', 'mask.pgm' ]
        # self.runCommand(command_args)


        # ##  -------
        # ## process 2: run CT algorithm
        # ## ---------
        # command_args = ['ctseg']  + ['input_0.pgm'] + ['mask.pgm']
        # command_args += [str(self.cfg['param']['lambda'])]


        # self.runCommand(command_args, stdOut=stdout, stdErr=stdout)

        # ## ---------
        # ## process 3: converting to output result
        # ## ---------
        # command_args = ['convert.sh', 'result.pgm', 'result.png']
        # self.runCommand(command_args)


        resultHeight =  min (600, size[1])
        self.cfg['param']['imageheightresized'] = resultHeight
        self.cfg['param']['resultheight'] = max (200, resultHeight)

        ## ------
        # Save version num:
        fVersion = open(self.work_dir+"version.txt", "w")
        command_args = ['ipolDemo', '--version']
        self.runCommand(command_args, fVersion,None )
        fVersion.close()
        f = open(self.work_dir+"version.txt", "r")
        self.cfg['param']['version'] = f.read()
        self.cfg.save()

        
        # ## ----
        # ## Final step: save command line
        # ## ----
        # f = open(self.work_dir+"commands.txt", "w")
        # f.write(self.list_commands)
        # f.close()



    def runCommand(self, command, stdOut=None, stdErr=None, comp=None):
        """
        Run command and update the attribute list_commands
        """
        p = self.run_proc(command, stderr=stdErr, stdout=stdOut, \
                          env={'LD_LIBRARY_PATH' : self.bin_dir})
        self.wait_proc(p, timeout=self.timeout)
        index = 0
        # transform convert.sh in it classic prog command (equivalent)
        for arg in command:
            if arg == "convert.sh" :
                command[index] = "convert"
            index = index + 1
        command_to_save = ' '.join(['"' + arg + '"' if ' ' in arg else arg
                 for arg in command ])
        if comp is not None:
            command_to_save += comp
        self.list_commands +=  command_to_save + '\n'
        return command_to_save
