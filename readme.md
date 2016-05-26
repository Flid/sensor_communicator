# What is that?

A part of my "Smar}{ouse" project, responsible for communications with 
the real world (hardware sensors and web-services).

Why do we need a separate service for that? Because:

* It has to be python2.7, as there are lots of libraries with C-extensions,
  which do not support python3. I do not want to patch them all.
* It allows to decrease the number of requests to external
  services and make consumers' work more smooth by returning a freshly cached data.
* Dividing a code into logical pieces is good!

# Currently supported functionality

* DHT22 temperature/humidity sensor.
* Endomondo client, get the information about workouts and computes some stats.
* Weather client, get the current weather in Bristol and rain forecast.
* Wireless NRF24L01+ transmitter support. Creates an abstract of wireless devices, 
that can be manipulated separately. 
  Currently supported wireless devices:  
  * Power switch to turn on/off a remote device. [link](https://github.com/Flid/wireless_devices/tree/master/PowerControl)
   
   Planned devices:  
  * Outdoor weather sensor
  * [Bike computer](https://github.com/Flid/wireless_devices/tree/master/BikeComputer)
  

# Terms and conditions.

Really? Ok, I have to write something about that. I wrote it just for fun, so if 
you accidentally find something interesting - just use it. It would be nice to notify 
me in this case, I will be happy to help with deployment and updates.
