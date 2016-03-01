<!DOCTYPE html>
<html lang="en">
  <head>
    <script src='https://code.jquery.com/jquery-2.2.1.min.js'></script>
    <script src='https://cdnjs.cloudflare.com/ajax/libs/flot/0.8.3/jquery.flot.js'></script>
	<script>
	//var max_time = 10;
	var current_time = 0;
	var running_data = {}; //array of arrays of x,y coords
	var interval = 200; //millisecond

	function get_data() {
		$.ajax(url='http://129.130.45.205:5000/data').done(function(data) {
			var raw_data = JSON.parse(data);
			for (var key in raw_data) {
				if (raw_data.hasOwnProperty(key)) {
	//				console.log(key, raw_data[key]);
				
					if(typeof(running_data[key]) === "undefined") running_data[key] = []
						running_data[key].push([current_time, raw_data[key]*8/1024.0/1024/1024]);
				
				}
			}
		});
		var values = Object.keys(running_data).map(function(key){
			return running_data[key];
		});
		console.log(values);
		$.plot("#placeholder", values);
		current_time+=(interval/1000.0);
	//	if(current_time > max_time) {
	//		current_time = 0;
	//		running_data = {};
	//	}
		setTimeout(get_data, interval);
	}
	setTimeout(get_data, interval);

	</script>
    <meta charset="utf-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- The above 3 meta tags *must* come first in the head; any other head content must come *after* these tags -->
    <meta name="description" content="">
    <meta name="author" content="">
    <link rel="icon" href="../../favicon.ico">

    <title>Starter Template for Bootstrap</title>

    <!-- Bootstrap core CSS -->
    <link href="/home/server/DynamicDMZController/pox/ext/templates/dist/css/bootstrap.min.css" rel="stylesheet">

    <!-- IE10 viewport hack for Surface/desktop Windows 8 bug -->
    <link href="../../assets/css/ie10-viewport-bug-workaround.css" rel="stylesheet">

    <!-- Custom styles for this template -->
    <link href="starter-template.css" rel="stylesheet">

    <!-- Just for debugging purposes. Don't actually copy these 2 lines! -->
    <!--[if lt IE 9]><script src="../../assets/js/ie8-responsive-file-warning.js"></script><![endif]-->
    <script src="../../assets/js/ie-emulation-modes-warning.js"></script>

    <!-- HTML5 shim and Respond.js for IE8 support of HTML5 elements and media queries -->
    <!--[if lt IE 9]>
      <script src="https://oss.maxcdn.com/html5shiv/3.7.2/html5shiv.min.js"></script>
      <script src="https://oss.maxcdn.com/respond/1.4.2/respond.min.js"></script>
    <![endif]-->
  </head>

  <body>

    <nav class="navbar navbar-inverse navbar-fixed-top">
      <div class="container">
        <div class="navbar-header">
          <button type="button" class="navbar-toggle collapsed" data-toggle="collapse" data-target="#navbar" aria-expanded="false" aria-controls="navbar">
            <span class="sr-only">Toggle navigation</span>
            <span class="icon-bar"></span>
            <span class="icon-bar"></span>
            <span class="icon-bar"></span>
          </button>
          <a class="navbar-brand" href="#">Project name</a>
        </div>
        <div id="navbar" class="collapse navbar-collapse">
          <ul class="nav navbar-nav">
            <li class="active"><a href="#">Home</a></li>
            <li><a href="#about">About</a></li>
            <li><a href="#contact">Contact</a></li>
          </ul>
        </div><!--/.nav-collapse -->
      </div>
    </nav>

    <div class="container">

      <div class="starter-template">
        <h1>Flow Bandwidth</h1>
        <p class="lead">Y axis in Gbps.</p>
      </div>
	<div id="placeholder" style="width:700px;height:500px;"></div>
    </div><!-- /.container -->
<div id="placeholder" style="width:700px;height:500px;"></div>

    <!-- Bootstrap core JavaScript
    ================================================== -->
    <!-- Placed at the end of the document so the pages load faster -->
    <script src="https://ajax.googleapis.com/ajax/libs/jquery/1.11.3/jquery.min.js"></script>
    <script>window.jQuery || document.write('<script src="../../assets/js/vendor/jquery.min.js"><\/script>')</script>
    <script src="/home/server/DynamicDMZController/pox/ext/templates/dist/js/bootstrap.min.js"></script>
    <!-- IE10 viewport hack for Surface/desktop Windows 8 bug -->
    <script src="../../assets/js/ie10-viewport-bug-workaround.js"></script>
  </body>
</html>

